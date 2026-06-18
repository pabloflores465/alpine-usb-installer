from __future__ import annotations

import argparse
import contextlib
import getpass
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from alpine_usb.apk_packages.index import (
    APK_SEARCH_REPOS,
    search_official_apk_packages,
    validate_branch,
    validate_package_name,
)
from alpine_usb.build_profiles.presets import VALID_WMS, apply_profile_defaults
from alpine_usb.images.validation import validate_usb_image
from alpine_usb.rhel_packages.packages import (
    RHEL_DEFAULT_RELEASE,
    RHEL_VALID_WMS,
    normalize_rhel_distro,
    resolve_rhel_packages,
    search_rhel_packages,
    validate_rhel_release,
)
from alpine_usb.usb_devices.detection import device_safety_report, list_devices, selected_device

APP_TITLE = "Linux USB Installer"
DEFAULT_IMAGE_NAME = "linux-usb.img"
TERMINAL_ENTRYPOINT = "alpine-usb"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
_TERMINAL_RUNTIME_DIR: Path | None = None
TERMINAL_RUNTIME_RESOURCES = (
    "build-alpine-usb.sh",
    "configure-alpine-usb.sh",
    "configure-rhel-usb.sh",
    "build-rhel-usb.sh",
    "README.md",
    "LICENSE",
    "efi-fallback",
    "scripts/Dockerfile.builder",
)


class Colors:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.reset = "\033[0m" if enabled else ""
        self.bold = "\033[1m" if enabled else ""
        self.dim = "\033[2m" if enabled else ""
        self.blue = "\033[94m" if enabled else ""
        self.cyan = "\033[96m" if enabled else ""
        self.green = "\033[92m" if enabled else ""
        self.yellow = "\033[93m" if enabled else ""
        self.red = "\033[91m" if enabled else ""
        self.magenta = "\033[95m" if enabled else ""


C = Colors(sys.stdout.isatty() and os.environ.get("NO_COLOR") is None)


def c(text: str, color: str) -> str:
    return f"{color}{text}{C.reset}" if C.enabled else text


def info(msg: str):
    print(f"{c('›', C.cyan)} {msg}", flush=True)


def ok(msg: str):
    print(f"{c('✓', C.green)} {msg}", flush=True)


def warn(msg: str):
    print(f"{c('⚠', C.yellow)} {msg}", flush=True)


def err(msg: str):
    print(f"{c('✗', C.red)} {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, **kwargs)


def can_write_to_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write-test-{os.getpid()}"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def secure_runtime_dir(name: str) -> Path:
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    base = Path(tempfile.gettempdir()) / f"alpine-usb-installer-{uid}"
    for path in [base, base / name]:
        if path.is_symlink():
            raise RuntimeError(f"Refusing symlinked runtime path: {path}")
        if path.exists():
            st = path.stat()
            if hasattr(os, "getuid") and st.st_uid != os.getuid():
                raise RuntimeError(f"Refusing runtime path not owned by current user: {path}")
            if stat.S_IMODE(st.st_mode) & 0o077:
                path.chmod(0o700)
        else:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    return base / name


def prepare_terminal_runtime(source_dir: Path) -> Path:
    runtime = secure_runtime_dir("terminal-runtime")
    for name in TERMINAL_RUNTIME_RESOURCES:
        src = source_dir / name
        dst = runtime / name
        if not src.exists():
            continue
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if name.endswith(".sh"):
                dst.chmod(0o755)
    (runtime / ".work").mkdir(exist_ok=True)
    return runtime


def repo_root() -> Path:
    global _TERMINAL_RUNTIME_DIR
    if _TERMINAL_RUNTIME_DIR is not None:
        return _TERMINAL_RUNTIME_DIR
    if getattr(sys, "frozen", False):
        _TERMINAL_RUNTIME_DIR = prepare_terminal_runtime(SOURCE_DIR)
        return _TERMINAL_RUNTIME_DIR
    if can_write_to_dir(SOURCE_DIR):
        return SOURCE_DIR
    _TERMINAL_RUNTIME_DIR = prepare_terminal_runtime(SOURCE_DIR)
    return _TERMINAL_RUNTIME_DIR


def terminal_entrypoint_name() -> str:
    name = Path(sys.argv[0]).name
    return name if name != "cli.py" else TERMINAL_ENTRYPOINT


def print_panel(title: str, rows: list[tuple[str, str] | str]):
    width = 88
    print(c(f"╭─ {title} " + "─" * max(0, width - len(title) - 4), C.blue))
    for row in rows:
        if isinstance(row, tuple):
            key, value = row
            print(c("│ ", C.blue) + f"{key:<24} {value}")
        else:
            print(c("│ ", C.blue) + row)
    print(c("╰" + "─" * width, C.blue))


def bool_env(value: bool) -> str:
    return "1" if value else "0"


def split_packages(values: list[str] | None, inline: str | None) -> str:
    packages: list[str] = []
    for item in values or []:
        packages.extend(part for part in re.split(r"\s+", item.strip()) if part)
    if inline:
        packages.extend(part for part in re.split(r"\s+", inline.strip()) if part)
    deduped: list[str] = []
    seen: set[str] = set()
    for pkg in packages:
        validate_package_name(pkg)
        if pkg not in seen:
            seen.add(pkg)
            deduped.append(pkg)
    return " ".join(deduped)


def build_distro(args: argparse.Namespace) -> str:
    raw = getattr(args, "distro", "alpine")
    if raw == "alpine":
        return "alpine"
    return normalize_rhel_distro(raw)


def env_from_build_args(args: argparse.Namespace) -> dict[str, str]:
    distro = build_distro(args)
    if distro == "alpine":
        validate_branch(args.branch)
    else:
        validate_rhel_release(getattr(args, "release", RHEL_DEFAULT_RELEASE))
    password = args.password
    root_password = args.root_password if args.root_password is not None else password
    wms = list(args.wm or [])
    if args.tiling_wms:
        wms.extend(part for part in re.split(r"[\s,]+", args.tiling_wms.strip()) if part)
    # Stable unique order.
    ordered_wms: list[str] = []
    for wm in wms:
        if wm not in ordered_wms:
            ordered_wms.append(wm)

    common = {
        "IMAGE_SIZE": args.image_size,
        "ARCH": args.arch,
    }
    if distro != "alpine":
        extra_packages = split_packages(args.extra_package, args.extra_packages)
        unsupported_wms = [wm for wm in ordered_wms if wm not in RHEL_VALID_WMS]
        if unsupported_wms:
            supported = ", ".join(RHEL_VALID_WMS)
            raise ValueError(f"RHEL-family builds currently support these WMs: {supported}")
        packages = resolve_rhel_packages(
            desktop=args.desktop,
            display_manager=args.display_manager,
            wms=ordered_wms,
            network=args.network,
            wifi=args.wifi,
            bluetooth=args.bluetooth,
            audio=args.audio,
            browser=args.browser,
            firmware=args.firmware,
            auto_resize=args.auto_resize,
            extra_packages=extra_packages,
        )
        return {
            **common,
            "IMAGE_NAME": f".rhel-usb-cli-{os.getpid()}.img",
            "LINUX_USB_DISTRO": distro,
            "RHEL_USB_DISTRO": distro,
            "RHEL_USB_RELEASE": getattr(args, "release", RHEL_DEFAULT_RELEASE),
            "RHEL_USB_PROFILE": getattr(args, "profile", "compatibility"),
            "RHEL_USB_USER": args.user,
            "RHEL_USB_PASSWORD": password,
            "RHEL_USB_ROOT_PASSWORD": root_password,
            "RHEL_USB_HOSTNAME": args.hostname,
            "RHEL_USB_TIMEZONE": args.timezone,
            "RHEL_USB_LOCALE": args.locale,
            "RHEL_USB_LANGUAGE": args.language or "",
            "RHEL_USB_CONSOLE_KEYMAP": args.console_keymap,
            "RHEL_USB_XKB_LAYOUT": args.xkb_layout,
            "RHEL_USB_XKB_VARIANT": args.xkb_variant,
            "RHEL_USB_XKB_MODEL": args.xkb_model,
            "RHEL_USB_DESKTOP": args.desktop,
            "RHEL_USB_TILING_WMS": " ".join(ordered_wms),
            "RHEL_USB_DEFAULT_SESSION": args.default_session,
            "RHEL_USB_DISPLAY_MANAGER": args.display_manager,
            "RHEL_USB_NETWORK": args.network,
            "RHEL_USB_WIFI": bool_env(args.wifi),
            "RHEL_USB_BLUETOOTH": bool_env(args.bluetooth),
            "RHEL_USB_AUDIO": args.audio,
            "RHEL_USB_BROWSER": args.browser,
            "RHEL_USB_FIRMWARE": args.firmware,
            "RHEL_USB_BOOTLOADER": args.bootloader,
            "RHEL_USB_KERNEL_FLAVOR": args.kernel,
            "RHEL_USB_BOOT_TIMEOUT": str(args.boot_timeout),
            "RHEL_USB_AUTO_RESIZE": bool_env(args.auto_resize),
            "RHEL_USB_EXTRA_PACKAGES": extra_packages,
            "RHEL_USB_PACKAGE_LIST": " ".join(packages),
        }

    return {
        **common,
        "IMAGE_NAME": f".alpine-usb-cli-{os.getpid()}.img",
        "LINUX_USB_DISTRO": "alpine",
        "ALPINE_USB_PROFILE": getattr(args, "profile", "compatibility"),
        "ALPINE_BRANCH": args.branch,
        "ALPINE_USB_USER": args.user,
        "ALPINE_USB_PASSWORD": password,
        "ALPINE_USB_ROOT_PASSWORD": root_password,
        "ALPINE_USB_HOSTNAME": args.hostname,
        "ALPINE_USB_TIMEZONE": args.timezone,
        "ALPINE_USB_LOCALE": args.locale,
        "ALPINE_USB_LANGUAGE": args.language or "",
        "ALPINE_USB_CONSOLE_KEYMAP": args.console_keymap,
        "ALPINE_USB_XKB_LAYOUT": args.xkb_layout,
        "ALPINE_USB_XKB_VARIANT": args.xkb_variant,
        "ALPINE_USB_XKB_MODEL": args.xkb_model,
        "ALPINE_USB_DESKTOP": args.desktop,
        "ALPINE_USB_TILING_WMS": " ".join(ordered_wms),
        "ALPINE_USB_DEFAULT_SESSION": args.default_session,
        "ALPINE_USB_DISPLAY_MANAGER": args.display_manager,
        "ALPINE_USB_NETWORK": args.network,
        "ALPINE_USB_WIFI": bool_env(args.wifi),
        "ALPINE_USB_BLUETOOTH": bool_env(args.bluetooth),
        "ALPINE_USB_AUDIO": args.audio,
        "ALPINE_USB_BROWSER": args.browser,
        "ALPINE_USB_FIRMWARE": args.firmware,
        "ALPINE_USB_LEGACY_X11_DRIVERS": bool_env(getattr(args, "legacy_x11_drivers", True)),
        "ALPINE_USB_BOOTLOADER": args.bootloader,
        "ALPINE_USB_KERNEL_FLAVOR": args.kernel,
        "ALPINE_USB_BOOT_TIMEOUT": str(args.boot_timeout),
        "ALPINE_USB_SYSTEMD_BOOT_CONSOLE_MODE": args.systemd_boot_console_mode,
        "ALPINE_USB_AUTO_RESIZE": bool_env(args.auto_resize),
        "ALPINE_USB_EXTRA_PACKAGES": split_packages(args.extra_package, args.extra_packages),
    }


def print_build_summary(env: dict[str, str], output: Path):
    if env.get("LINUX_USB_DISTRO") == "alpine":
        distro_row = ("Alpine", f"{env['ALPINE_BRANCH']} / {env['ARCH']}")
        prefix = "ALPINE_USB"
        profile = env.get("ALPINE_USB_PROFILE", "compatibility")
        boot = f"{env['ALPINE_USB_BOOTLOADER']} linux-{env['ALPINE_USB_KERNEL_FLAVOR']} firmware={env['ALPINE_USB_FIRMWARE']}"
        legacy_rows: list[tuple[str, str]] = [("Legacy X11 drivers", env.get("ALPINE_USB_LEGACY_X11_DRIVERS", "1"))]
        extra = env["ALPINE_USB_EXTRA_PACKAGES"] or "none"
    else:
        distro_row = ("RHEL-family", f"{env['RHEL_USB_DISTRO']} {env['RHEL_USB_RELEASE']} / {env['ARCH']}")
        prefix = "RHEL_USB"
        profile = env.get("RHEL_USB_PROFILE", "compatibility")
        boot = (
            f"{env['RHEL_USB_BOOTLOADER']} kernel={env['RHEL_USB_KERNEL_FLAVOR']} firmware={env['RHEL_USB_FIRMWARE']}"
        )
        legacy_rows = [("Package list", f"{len(env['RHEL_USB_PACKAGE_LIST'].split())} resolved packages/groups")]
        extra = env["RHEL_USB_EXTRA_PACKAGES"] or "none"
    rows = [
        ("Output", str(output)),
        ("Minimum image size", env["IMAGE_SIZE"]),
        distro_row,
        ("Profile", profile),
        ("Desktop", env[f"{prefix}_DESKTOP"]),
        ("Window managers", env[f"{prefix}_TILING_WMS"] or "none"),
        ("Default session", env[f"{prefix}_DEFAULT_SESSION"]),
        ("Display manager", env[f"{prefix}_DISPLAY_MANAGER"]),
        ("Network", f"{env[f'{prefix}_NETWORK']} wifi={env[f'{prefix}_WIFI']} bluetooth={env[f'{prefix}_BLUETOOTH']}"),
        ("Audio / browser", f"{env[f'{prefix}_AUDIO']} / {env[f'{prefix}_BROWSER']}"),
        ("Boot", boot),
        *legacy_rows,
        ("Auto-resize USB", env[f"{prefix}_AUTO_RESIZE"]),
        ("Keyboard", f"console={env[f'{prefix}_CONSOLE_KEYMAP']} xkb={env[f'{prefix}_XKB_LAYOUT']}"),
        ("Extra packages", extra),
    ]
    print_panel("Build profile", rows)


def confirm(prompt: str, yes: bool = False) -> bool:
    if yes:
        return True
    answer = input(f"{c('?', C.yellow)} {prompt} [y/N] ").strip().lower()
    return answer in {"y", "yes", "s", "si", "sí"}


SECRET_ENV_TO_FILE = {
    "ALPINE_USB_PASSWORD": "ALPINE_USB_PASSWORD_FILE",
    "ALPINE_USB_ROOT_PASSWORD": "ALPINE_USB_ROOT_PASSWORD_FILE",
    "RHEL_USB_PASSWORD": "RHEL_USB_PASSWORD_FILE",
    "RHEL_USB_ROOT_PASSWORD": "RHEL_USB_ROOT_PASSWORD_FILE",
}


def prepare_secret_env(env: dict[str, str]) -> tuple[dict[str, str], list[Path]]:
    safe_env = dict(env)
    created: list[Path] = []
    secret_dir = repo_root() / ".work" / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.chmod(0o700)
    for key, file_key in SECRET_ENV_TO_FILE.items():
        if key not in safe_env:
            continue
        value = safe_env.pop(key, "")
        path = secret_dir / f"{key.lower()}-{os.getpid()}.secret"
        path.write_text(value)
        path.chmod(0o600)
        safe_env[file_key] = str(path)
        created.append(path)
    return safe_env, created


def cleanup_secret_files(paths: list[Path]):
    for path in paths:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def run_config_dry_run(env: dict[str, str]) -> int:
    sys.stdout.flush()
    dry_env = os.environ.copy()
    safe_env, secret_files = prepare_secret_env(env)
    dry_env.update(safe_env)
    if env.get("LINUX_USB_DISTRO") == "alpine":
        script = "./configure-alpine-usb.sh"
        dry_env["ALPINE_USB_DRY_RUN"] = "1"
    else:
        script = "./configure-rhel-usb.sh"
        dry_env["RHEL_USB_DRY_RUN"] = "1"
    dry_env.pop("IMAGE_NAME", None)
    try:
        proc = subprocess.Popen([script], cwd=repo_root(), env=dry_env)
        return proc.wait()
    finally:
        cleanup_secret_files(secret_files)


def cmd_build(args: argparse.Namespace) -> int:
    if args.ask_password:
        args.password = getpass.getpass("User password: ")
        root_pw = getpass.getpass("Root password (empty = same as user): ")
        args.root_password = root_pw or args.password
    if not args.password:
        err("User password is required. Use --ask-password or --password.")
        return 2
    try:
        env = env_from_build_args(args)
    except ValueError as exc:
        err(str(exc))
        return 2
    output = Path(args.output).expanduser().resolve()
    print_build_summary(env, output)

    if args.dry_run:
        info("Dry-run only: validating generated Linux configuration and package list.")
        return run_config_dry_run(env)

    if output.exists() and not confirm(f"Overwrite existing image {output}?", args.yes):
        warn("Cancelled.")
        return 1
    if not confirm("Build this Linux USB image now?", args.yes):
        warn("Cancelled.")
        return 1

    build_env = os.environ.copy()
    safe_env, secret_files = prepare_secret_env(env)
    build_env.update(safe_env)
    build_env["OUTPUT_PATH"] = str(output)
    build_name = env["IMAGE_NAME"]
    built_path = repo_root() / build_name
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        if built_path.exists():
            built_path.unlink()
        if output.exists():
            output.unlink()
        info("Starting build. This can take a while…")
        sys.stdout.flush()
        script = "./build-alpine-usb.sh" if env.get("LINUX_USB_DISTRO") == "alpine" else "./build-rhel-usb.sh"
        proc = subprocess.Popen([script], cwd=repo_root(), env=build_env)
        code = proc.wait()
        if code != 0:
            err(f"Build failed with exit code {code}")
            return code
        if not output.exists():
            err(f"Build finished but expected image was not found: {output}")
            return 1
        ok(f"Image ready: {output}")
        return 0
    finally:
        cleanup_secret_files(secret_files)
        if built_path.exists() and built_path != output:
            with contextlib.suppress(OSError):
                built_path.unlink()


def cmd_search(args: argparse.Namespace) -> int:
    try:
        distro = build_distro(args)
        if distro == "alpine":
            validate_branch(args.branch)
            info(f"Searching Alpine {args.branch}/{args.arch} official repos: {', '.join(APK_SEARCH_REPOS)}")
            results = search_official_apk_packages(args.branch, args.arch, args.query, args.limit)
        else:
            release = validate_rhel_release(args.release)
            info(f"Searching RHEL-family packages for {distro} {release} with dnf repoquery")
            results = search_rhel_packages(distro, release, args.query, args.limit)
    except ValueError as exc:
        err(str(exc))
        return 2
    except Exception as exc:
        err(f"Package search failed: {exc}")
        return 1
    if not results:
        warn(f"No packages found for: {args.query}")
        return 1
    rows: list[tuple[str, str] | str] = []
    for idx, package in enumerate(results, 1):
        name = c(package["name"], C.green)
        repo = c(package.get("repo", "?"), C.cyan)
        version = package.get("version", "")
        desc = package.get("description", "")
        rows.append((f"{idx:>2}. {name}", f"{version}  [{repo}]  {desc}"))
    print_panel(f"Top {len(results)} suggestions for '{args.query}'", rows)
    print("Add packages with:")
    print(c(f"  {terminal_entrypoint_name()} build --extra-package {results[0]['name']}", C.dim))
    return 0


def cmd_devices(_args: argparse.Namespace) -> int:
    devices = list_devices()
    if not devices:
        warn("No removable USB-like devices detected. You can still pass a device manually to flash.")
        return 1
    print_panel("USB devices", [(dev, label) for dev, label in devices])
    return 0


def cmd_flash(args: argparse.Namespace) -> int:
    image = Path(args.image).expanduser().resolve()
    dev = selected_device(args.device)
    if not image.exists():
        err(f"Image not found: {image}")
        return 1
    if not dev:
        err("Invalid target device.")
        return 1
    image_check = validate_usb_image(image)
    if not image_check.ok:
        err(image_check.reason or "Image failed validation.")
        return 1
    ok_safe, dev, device_rows, reason = device_safety_report(dev)
    if not ok_safe:
        err(reason or "Unsafe target device.")
        return 1

    print_panel(
        "Flash USB",
        [("Image", str(image)), ("Image size", f"{image.stat().st_size / 1_000_000_000:.1f} GB"), *device_rows],
    )
    if not args.yes:
        warn("This permanently erases the selected USB device.")
        typed = input(f"Type {c(f'ERASE {dev}', C.red)} to continue: ").strip()
        if typed != f"ERASE {dev}":
            warn("Cancelled.")
            return 1

    sysname = platform.system()
    if sysname == "Darwin":
        raw = dev.replace("/dev/disk", "/dev/rdisk")
        cmd = ["sudo", "dd", f"if={image}", f"of={raw}", "bs=16m", "status=progress"]
        subprocess.run(["diskutil", "unmountDisk", dev])
        code = subprocess.call(cmd)
        subprocess.run(["sync"])
        subprocess.run(["diskutil", "eject", dev])
        return code
    if sysname == "Linux":
        cmd = ["dd", f"if={image}", f"of={dev}", "bs=16M", "iflag=fullblock", "status=progress", "conv=fsync"]
        if os.geteuid() != 0:
            cmd.insert(0, shutil.which("pkexec") or "sudo")
        return subprocess.call(cmd)
    err("Windows flashing is not implemented. Use Rufus/balenaEtcher with the generated image.")
    return 1


def cmd_doctor(_args: argparse.Namespace) -> int:
    sysname = platform.system()
    checks = []
    if sysname == "Darwin":
        checks.append(("docker", shutil.which("docker") is not None))
        if shutil.which("docker"):
            checks.append(
                (
                    "docker running",
                    run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
                )
            )
        checks.append(("diskutil", shutil.which("diskutil") is not None))
    elif sysname == "Linux":
        for name in ["sudo", "python3", "mmd", "mcopy", "mdir", "grub-mkstandalone", "dd", "lsblk"]:
            checks.append((name, shutil.which(name) is not None))
    else:
        checks.append(("unsupported OS for flashing", False))

    failed = False
    rows = []
    for name, good in checks:
        rows.append((name, c("OK", C.green) if good else c("missing", C.red)))
        failed = failed or not good
    print_panel("Host checks", rows)
    return 1 if failed else 0


def cmd_tui(args: argparse.Namespace) -> int:
    from tui import main as tui_main

    tui_args = []
    if getattr(args, "self_test", False):
        tui_args.append("--self-test")
    return tui_main(tui_args)


def add_common_build_options(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--profile",
        default="compatibility",
        choices=["compatibility", "minimal"],
        help="Build preset. minimal changes defaults unless explicitly overridden.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(Path(tempfile.gettempdir()) / "alpine-usb-installer" / DEFAULT_IMAGE_NAME),
        help="Final output image path",
    )
    parser.add_argument("-s", "--image-size", default="16G", help="Minimum image size used for the build, e.g. 16G")
    parser.add_argument(
        "--distro",
        default="alpine",
        choices=["alpine", "rhel", "rocky", "alma", "centos-stream"],
        help="Linux distribution backend",
    )
    parser.add_argument("--branch", default="latest-stable", help="Alpine branch: latest-stable, edge, v3.22, ...")
    parser.add_argument(
        "--release",
        default=RHEL_DEFAULT_RELEASE,
        help="RHEL-family major release (default: Rocky/Alma/CentOS Stream 9)",
    )
    parser.add_argument("--arch", default="x86_64", choices=["x86_64"], help="Target architecture")
    parser.add_argument("--hostname", default="alpine-usb")
    parser.add_argument("--user", default="alpine")
    parser.add_argument(
        "--password", default=None, help="Initial user password (use --ask-password to avoid shell history)"
    )
    parser.add_argument("--root-password", default=None, help="Initial root password; default is user password")
    parser.add_argument("--ask-password", action="store_true", help="Prompt for passwords interactively")
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--locale", default="en_US.UTF-8")
    parser.add_argument("--language", default="")
    parser.add_argument("--console-keymap", default="us")
    parser.add_argument("--xkb-layout", default="us")
    parser.add_argument("--xkb-variant", default="")
    parser.add_argument("--xkb-model", default="pc105")
    parser.add_argument("--desktop", default="xfce", choices=["xfce", "gnome", "plasma", "mate", "lxqt", "none"])
    parser.add_argument(
        "--display-manager", default="auto", choices=["auto", "lightdm", "sddm", "gdm", "lxdm", "greetd", "none"]
    )
    parser.add_argument(
        "--default-session",
        default="auto",
        choices=["auto", "xfce", "gnome", "plasma", "mate", "lxqt", *VALID_WMS, "shell"],
    )
    parser.add_argument("--wm", action="append", choices=VALID_WMS, help="Add optional window manager; can be repeated")
    parser.add_argument("--tiling-wms", default="", help="Optional comma/space separated WM list")
    parser.add_argument("--browser", default="firefox", choices=["firefox-esr", "firefox", "chromium", "none"])
    parser.add_argument("--audio", default="pipewire", choices=["pipewire", "alsa", "none"])
    parser.add_argument("--network", default="networkmanager", choices=["networkmanager", "none"])
    parser.add_argument("--wifi", dest="wifi", action="store_true", default=True)
    parser.add_argument("--no-wifi", dest="wifi", action="store_false")
    parser.add_argument("--bluetooth", dest="bluetooth", action="store_true", default=True)
    parser.add_argument("--no-bluetooth", dest="bluetooth", action="store_false")
    parser.add_argument("--bootloader", default="grub", choices=["grub", "systemd-boot"])
    parser.add_argument("--kernel", default="lts", choices=["lts", "stable"])
    parser.add_argument("--firmware", default="full", choices=["full", "none"])
    parser.add_argument(
        "--legacy-x11-drivers",
        dest="legacy_x11_drivers",
        action="store_true",
        default=True,
        help="Install broad legacy Xorg video drivers for maximum compatibility",
    )
    parser.add_argument(
        "--no-legacy-x11-drivers",
        dest="legacy_x11_drivers",
        action="store_false",
        help="Skip legacy Xorg video drivers for smaller/faster images",
    )
    parser.add_argument("--boot-timeout", type=int, default=3)
    parser.add_argument(
        "--systemd-boot-console-mode", default="max", help="systemd-boot console-mode: max, auto, keep or numeric mode"
    )
    parser.add_argument("--auto-resize", dest="auto_resize", action="store_true", default=True)
    parser.add_argument("--no-auto-resize", dest="auto_resize", action="store_false")
    parser.add_argument(
        "--extra-package", action="append", help="Extra distro package; can be repeated or contain spaces"
    )
    parser.add_argument("--extra-packages", default="", help="Space-separated extra distro packages")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and print generated package list without building"
    )
    parser.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Unified terminal interface for Alpine and RHEL-family Linux USB images (TUI + CLI commands).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser(
        "build", help="Build a configurable Linux USB image", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    add_common_build_options(build)
    build.set_defaults(func=cmd_build)

    search = sub.add_parser(
        "search",
        help="Search Alpine or RHEL-family packages and show top suggestions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    search.add_argument("query")
    search.add_argument("--distro", default="alpine", choices=["alpine", "rhel", "rocky", "alma", "centos-stream"])
    search.add_argument("--branch", default="latest-stable")
    search.add_argument("--release", default=RHEL_DEFAULT_RELEASE)
    search.add_argument("--arch", default="x86_64")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    devices = sub.add_parser("devices", help="List removable USB devices")
    devices.set_defaults(func=cmd_devices)

    flash = sub.add_parser(
        "flash", help="Flash an image to a USB device", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    flash.add_argument("image")
    flash.add_argument("device")
    flash.add_argument("-y", "--yes", action="store_true", help="Skip ERASE confirmation")
    flash.set_defaults(func=cmd_flash)

    doctor = sub.add_parser("doctor", help="Check host tools needed for build/flash")
    doctor.set_defaults(func=cmd_doctor)

    tui = sub.add_parser("tui", help="Open the complete interactive terminal UI (default when run without arguments)")
    tui.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    tui.set_defaults(func=cmd_tui)
    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    if not argv:
        if sys.stdin.isatty() and sys.stdout.isatty():
            argv = ["tui"]
        else:
            parser.print_help()
            return 0
    args = parser.parse_args(argv)
    apply_profile_defaults(args, argv)
    if args.command != "tui":
        print(c(f"\n{APP_TITLE}", C.bold + C.cyan))
        print(c("─" * len(APP_TITLE), C.cyan), flush=True)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        warn("Interrupted.")
        return 130


if __name__ == "__main__":
    print(f"cli.py is import-only. Run ./{TERMINAL_ENTRYPOINT} (or ./{TERMINAL_ENTRYPOINT} tui).", file=sys.stderr)
    raise SystemExit(2)
