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

from alpine_usb.build_profiles.presets import VALID_WMS, apply_profile_defaults
from alpine_usb.images.validation import validate_usb_image
from alpine_usb.linux_distros import DISTROS, DistroProvider, distro_choices, get_distro, rhel_variant_for_name
from alpine_usb.linux_distros.fedora import plan_from_options as fedora_plan_from_options
from alpine_usb.nixos.build import env_to_config as nixos_env_to_config
from alpine_usb.nixos.build import run_nixos_build, run_nixos_dry_run
from alpine_usb.nixos.build import summary_rows as nixos_summary_rows
from alpine_usb.rhel_packages.packages import resolve_rhel_packages
from alpine_usb.usb_devices.detection import device_safety_report, list_devices, selected_device

APP_TITLE = "LEDIT"
APP_DESCRIPTION = "Linux External Drive Installer Tool"
DEFAULT_IMAGE_NAME = "ledit.img"
TERMINAL_ENTRYPOINT = "ledit"
LEGACY_TERMINAL_ENTRYPOINT = "alpine-usb"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "ledit"
_TERMINAL_RUNTIME_DIR: Path | None = None

BUILD_SCRIPT_RESOURCES = tuple(
    sorted(
        {
            script
            for provider in DISTROS.values()
            for script in (provider.build_script, provider.configure_script)
            if script
        }
    )
)
TERMINAL_RUNTIME_RESOURCES = (
    *BUILD_SCRIPT_RESOURCES,
    "README.md",
    "LICENSE",
    "efi-fallback",
    "scripts/Dockerfile.builder",
    "scripts/Dockerfile.gentoo-builder",
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
    base = Path(tempfile.gettempdir()) / f"ledit-{uid}"
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


def _arg_was_passed(argv: list[str], name: str) -> bool:
    return any(token == name or token.startswith(name + "=") for token in argv)


def selected_provider(args: argparse.Namespace) -> DistroProvider:
    return get_distro(getattr(args, "distro", "alpine"))


def release_override(args: argparse.Namespace) -> str | None:
    return getattr(args, "release", None) or getattr(args, "nixos_channel", None)


def apply_distro_defaults(args: argparse.Namespace, argv: list[str]) -> None:
    if getattr(args, "command", None) not in {"build", "search"}:
        return
    provider = selected_provider(args)
    explicit_branch = _arg_was_passed(argv, "--branch") or _arg_was_passed(argv, "--release")
    explicit_user = _arg_was_passed(argv, "--user")
    explicit_hostname = _arg_was_passed(argv, "--hostname")
    explicit_output = _arg_was_passed(argv, "--output") or _arg_was_passed(argv, "-o")
    explicit_arch = _arg_was_passed(argv, "--arch")
    args._explicit_user = explicit_user
    args._explicit_hostname = explicit_hostname
    args._explicit_output = explicit_output
    args._explicit_branch = explicit_branch
    args._explicit_arch = explicit_arch
    override = release_override(args)
    if override:
        args.branch = override
    elif provider.id != "alpine" and not explicit_branch:
        args.branch = provider.default_branch
    if getattr(args, "command", None) == "build":
        if provider.id != "alpine" and not explicit_user:
            args.user = provider.default_user
        if provider.id != "alpine" and not explicit_hostname:
            args.hostname = provider.default_hostname
        if not explicit_arch:
            args.arch = provider.default_arch
        if not explicit_output:
            args.output = str(DEFAULT_OUTPUT_DIR / provider.default_image_name)
        if (
            provider.supports_extlinux
            and getattr(args, "bootloader", "grub") == "grub"
            and not _arg_was_passed(argv, "--bootloader")
        ):
            args.bootloader = "extlinux"


def split_packages(values: list[str] | None, inline: str | None, distro: str = "alpine") -> str:
    provider = get_distro(distro)
    packages: list[str] = []
    for item in values or []:
        packages.extend(part for part in re.split(r"\s+", item.strip()) if part)
    if inline:
        packages.extend(part for part in re.split(r"\s+", inline.strip()) if part)
    deduped: list[str] = []
    seen: set[str] = set()
    for pkg in packages:
        provider.validate_package_name(pkg)
        if pkg not in seen:
            seen.add(pkg)
            deduped.append(pkg)
    return " ".join(deduped)


def _ordered_wms(args: argparse.Namespace) -> list[str]:
    wms = list(getattr(args, "wm", None) or [])
    tiling_wms = getattr(args, "tiling_wms", "") or ""
    if tiling_wms:
        wms.extend(part for part in re.split(r"[\s,]+", tiling_wms.strip()) if part)
    ordered: list[str] = []
    for wm in wms:
        if wm not in ordered:
            ordered.append(wm)
    return ordered


def _common_env(args: argparse.Namespace, prefix: str, extra_packages: str) -> dict[str, str]:
    password = getattr(args, "password", "") or ""
    root_password = (
        getattr(args, "root_password", None) if getattr(args, "root_password", None) is not None else password
    )
    return {
        f"{prefix}_PROFILE": getattr(args, "profile", "compatibility"),
        f"{prefix}_USER": args.user,
        f"{prefix}_PASSWORD": password,
        f"{prefix}_ROOT_PASSWORD": root_password,
        f"{prefix}_HOSTNAME": args.hostname,
        f"{prefix}_TIMEZONE": args.timezone,
        f"{prefix}_LOCALE": args.locale,
        f"{prefix}_LANGUAGE": args.language or "",
        f"{prefix}_CONSOLE_KEYMAP": args.console_keymap,
        f"{prefix}_XKB_LAYOUT": args.xkb_layout,
        f"{prefix}_XKB_VARIANT": args.xkb_variant,
        f"{prefix}_XKB_MODEL": args.xkb_model,
        f"{prefix}_DESKTOP": args.desktop,
        f"{prefix}_TILING_WMS": " ".join(_ordered_wms(args)),
        f"{prefix}_DEFAULT_SESSION": args.default_session,
        f"{prefix}_DISPLAY_MANAGER": args.display_manager,
        f"{prefix}_NETWORK": args.network,
        f"{prefix}_WIFI": bool_env(args.wifi),
        f"{prefix}_BLUETOOTH": bool_env(args.bluetooth),
        f"{prefix}_AUDIO": args.audio,
        f"{prefix}_BROWSER": args.browser,
        f"{prefix}_FIRMWARE": args.firmware,
        f"{prefix}_LEGACY_X11_DRIVERS": bool_env(getattr(args, "legacy_x11_drivers", True)),
        f"{prefix}_BOOTLOADER": args.bootloader,
        f"{prefix}_KERNEL_FLAVOR": args.kernel,
        f"{prefix}_BOOT_TIMEOUT": str(args.boot_timeout),
        f"{prefix}_SYSTEMD_BOOT_CONSOLE_MODE": args.systemd_boot_console_mode,
        f"{prefix}_AUTO_RESIZE": bool_env(args.auto_resize),
        f"{prefix}_EXTRA_PACKAGES": extra_packages,
    }


def _normalize_identity_defaults(args: argparse.Namespace, provider: DistroProvider) -> None:
    if provider.id == "alpine":
        return
    if not getattr(args, "_explicit_user", False) and getattr(args, "user", "alpine") == "alpine":
        args.user = provider.default_user
    if not getattr(args, "_explicit_hostname", False) and getattr(args, "hostname", "alpine-usb") == "alpine-usb":
        args.hostname = provider.default_hostname
    if not getattr(args, "_explicit_arch", False) and getattr(args, "arch", "x86_64") == "x86_64":
        args.arch = provider.default_arch


def env_from_build_args(args: argparse.Namespace) -> dict[str, str]:
    provider = selected_provider(args)
    _normalize_identity_defaults(args, provider)
    branch = provider.normalize_branch(getattr(args, "branch", provider.default_branch))
    arch = provider.normalize_arch(getattr(args, "arch", provider.default_arch))
    if args.bootloader == "extlinux" and not provider.supports_extlinux:
        raise ValueError(f"{provider.label} does not support extlinux from LEDIT; choose grub or systemd-boot")
    if args.bootloader == "systemd-boot" and not provider.supports_systemd_boot:
        raise ValueError(f"{provider.label} backend currently supports GRUB only; choose --bootloader grub")

    extra_packages = split_packages(args.extra_package, args.extra_packages, provider.id)
    env: dict[str, str] = {
        "IMAGE_NAME": f".{provider.id}-usb-cli-{os.getpid()}.img",
        "IMAGE_SIZE": args.image_size,
        "ARCH": arch,
        "LINUX_USB_DISTRO": provider.id,
        "LEDIT_DISTRO": provider.id,
        provider.branch_env: branch,
    }
    if provider.id == "alpine":
        env["ALPINE_BRANCH"] = branch
    elif provider.id == "void":
        env["ALPINE_BRANCH"] = branch
        env["VOID_USB_EXTRA_PACKAGES"] = extra_packages
    elif provider.id == "rhel":
        env["RHEL_USB_DISTRO"] = rhel_variant_for_name(getattr(args, "distro", "rhel"))
    elif provider.id == "arch":
        env["ARCH_USB_BRANCH"] = branch
    elif provider.id == "nixos":
        env["NIXOS_CHANNEL"] = branch
        env["ALPINE_BRANCH"] = branch

    env.update(_common_env(args, provider.script_prefix, extra_packages))
    if provider.env_prefix != provider.script_prefix:
        env.update(_common_env(args, provider.env_prefix, extra_packages))

    if provider.id == "fedora":
        plan = fedora_plan_from_options(
            release=branch,
            arch=arch,
            desktop=args.desktop,
            display_manager=args.display_manager,
            default_session=args.default_session,
            wms=_ordered_wms(args),
            network=args.network,
            wifi=args.wifi,
            bluetooth=args.bluetooth,
            audio=args.audio,
            browser=args.browser,
            firmware=args.firmware,
            kernel=args.kernel,
            bootloader=args.bootloader,
            auto_resize=args.auto_resize,
            legacy_x11_drivers=getattr(args, "legacy_x11_drivers", True),
            extra_packages=extra_packages,
        )
        env.update(
            {
                "FEDORA_RELEASE": plan.release,
                "FEDORA_USB_PACKAGES": " ".join(plan.packages),
                "FEDORA_USB_GROUPS": " ".join(plan.groups),
                "FEDORA_USB_SERVICES": " ".join(plan.enabled_services),
                "FEDORA_USB_DEFAULT_TARGET": plan.default_target,
                "FEDORA_USB_WARNINGS": "\n".join(plan.warnings),
                "FEDORA_USB_DISPLAY_MANAGER": plan.display_manager,
                "FEDORA_USB_DEFAULT_SESSION": plan.default_session,
            }
        )
    elif provider.id == "rhel":
        env["RHEL_USB_PACKAGE_LIST"] = " ".join(
            resolve_rhel_packages(
                desktop=args.desktop,
                display_manager=args.display_manager,
                wms=_ordered_wms(args),
                network=args.network,
                wifi=args.wifi,
                bluetooth=args.bluetooth,
                audio=args.audio,
                browser=args.browser,
                firmware=args.firmware,
                auto_resize=args.auto_resize,
                extra_packages=extra_packages,
            )
        )
    return env


def print_build_summary(env: dict[str, str], output: Path):
    provider = get_distro(env.get("LINUX_USB_DISTRO", "alpine"))
    prefix = provider.script_prefix
    branch = env.get(provider.branch_env) or env.get("ALPINE_BRANCH") or provider.default_branch
    rows = [
        ("Output", str(output)),
        ("Minimum image size", env["IMAGE_SIZE"]),
        ("Distribution", f"{provider.label} {branch} / {env['ARCH']}"),
        ("Profile", env.get(f"{prefix}_PROFILE", "compatibility")),
        ("Desktop", env[f"{prefix}_DESKTOP"]),
        ("Window managers", env[f"{prefix}_TILING_WMS"] or "none"),
        ("Default session", env[f"{prefix}_DEFAULT_SESSION"]),
        ("Display manager", env[f"{prefix}_DISPLAY_MANAGER"]),
        ("Network", f"{env[f'{prefix}_NETWORK']} wifi={env[f'{prefix}_WIFI']} bluetooth={env[f'{prefix}_BLUETOOTH']}"),
        ("Audio / browser", f"{env[f'{prefix}_AUDIO']} / {env[f'{prefix}_BROWSER']}"),
        (
            "Boot",
            f"{env[f'{prefix}_BOOTLOADER']} linux-{env[f'{prefix}_KERNEL_FLAVOR']} firmware={env[f'{prefix}_FIRMWARE']}",
        ),
        ("Legacy X11 drivers", env.get(f"{prefix}_LEGACY_X11_DRIVERS", "1")),
        ("Auto-resize USB", env[f"{prefix}_AUTO_RESIZE"]),
        ("Keyboard", f"console={env[f'{prefix}_CONSOLE_KEYMAP']} xkb={env[f'{prefix}_XKB_LAYOUT']}"),
        ("Extra packages", env[f"{prefix}_EXTRA_PACKAGES"] or "none"),
    ]
    print_panel("Build profile", rows)


def confirm(prompt: str, yes: bool = False) -> bool:
    if yes:
        return True
    answer = input(f"{c('?', C.yellow)} {prompt} [y/N] ").strip().lower()
    return answer in {"y", "yes", "s", "si", "sí"}


def secret_env_to_file() -> dict[str, str]:
    prefixes = {provider.script_prefix for provider in DISTROS.values()} | {
        provider.env_prefix for provider in DISTROS.values()
    }
    return {
        **{f"{prefix}_PASSWORD": f"{prefix}_PASSWORD_FILE" for prefix in prefixes},
        **{f"{prefix}_ROOT_PASSWORD": f"{prefix}_ROOT_PASSWORD_FILE" for prefix in prefixes},
    }


SECRET_ENV_TO_FILE = secret_env_to_file()


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
    provider = get_distro(env.get("LINUX_USB_DISTRO", "alpine"))
    if provider.id == "nixos":
        return run_nixos_dry_run(nixos_env_to_config(env))
    dry_env = os.environ.copy()
    safe_env, secret_files = prepare_secret_env(env)
    dry_env.update(safe_env)
    dry_env.pop("IMAGE_NAME", None)
    dry_env[f"{provider.script_prefix}_DRY_RUN"] = "1"
    dry_env[f"{provider.env_prefix}_DRY_RUN"] = "1"
    try:
        if provider.configure_script:
            script = provider.configure_script_path(repo_root())
            assert script is not None
            script.chmod(0o755)
            proc = subprocess.Popen([f"./{script.name}"], cwd=repo_root(), env=dry_env)
        else:
            script = provider.build_script_path(repo_root())
            if script is None:
                raise RuntimeError(f"No dry-run adapter configured for {provider.label}")
            script.chmod(0o755)
            proc = subprocess.Popen([f"./{script.name}", "--dry-run"], cwd=repo_root(), env=dry_env)
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
    provider = get_distro(env.get("LINUX_USB_DISTRO", "alpine"))
    output = Path(args.output).expanduser().resolve()
    if provider.id == "nixos":
        config = nixos_env_to_config(env)
        print_panel("NixOS build profile", nixos_summary_rows(config, output))
        if args.dry_run:
            return run_nixos_dry_run(config)
        if output.exists() and not confirm(f"Overwrite existing image {output}?", args.yes):
            warn("Cancelled.")
            return 1
        if not confirm("Build this NixOS USB image now?", args.yes):
            warn("Cancelled.")
            return 1
        return run_nixos_build(config, output)

    print_build_summary(env, output)
    if args.dry_run:
        info(f"Dry-run only: validating generated {provider.label} configuration and package list.")
        return run_config_dry_run(env)

    if output.exists() and not confirm(f"Overwrite existing image {output}?", args.yes):
        warn("Cancelled.")
        return 1
    if not confirm(f"Build this {provider.label} USB image now?", args.yes):
        warn("Cancelled.")
        return 1

    script = provider.build_script_path(repo_root())
    if script is None:
        err(f"No build adapter configured for {provider.label}")
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
        script.chmod(0o755)
        info("Starting build. This can take a while…")
        sys.stdout.flush()
        proc = subprocess.Popen([f"./{script.name}"], cwd=repo_root(), env=build_env)
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
    provider = selected_provider(args)
    branch = release_override(args) or args.branch
    try:
        branch = provider.normalize_branch(branch)
        arch = provider.normalize_arch(args.arch)
    except ValueError as exc:
        err(str(exc))
        return 2
    info(f"Searching {provider.repo_description(branch, arch)}")
    try:
        results = provider.search_packages(branch, arch, args.query, args.limit)
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
    print_panel(f"Top {len(results)} {provider.package_manager} suggestions for '{args.query}'", rows)
    print("Add packages with:")
    distro_arg = "" if provider.id == "alpine" else f" --distro {provider.id}"
    print(c(f"  {terminal_entrypoint_name()} build{distro_arg} --extra-package {results[0]['name']}", C.dim))
    return 0


def cmd_distros(_args: argparse.Namespace) -> int:
    rows: list[tuple[str, str]] = []
    for name in distro_choices(visible_only=True):
        provider = get_distro(name)
        rows.append((name, f"{provider.label} · {provider.branch_label}: {', '.join(provider.branch_choices)}"))
    print_panel("Supported Linux distributions", rows)
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
        for optional in ["debootstrap", "pacstrap", "dnf", "zypper", "xbps-install", "nix"]:
            checks.append((f"optional {optional}", shutil.which(optional) is not None))
    else:
        checks.append(("unsupported OS for flashing", False))

    failed = False
    rows = []
    for name, good in checks:
        rows.append((name, c("OK", C.green) if good else c("missing", C.red)))
        failed = failed or (not good and not name.startswith("optional "))
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
        "--distro",
        default="alpine",
        choices=distro_choices(include_aliases=True),
        help="Linux distribution backend",
    )
    parser.add_argument(
        "--profile",
        default="compatibility",
        choices=["compatibility", "minimal"],
        help="Build preset. minimal changes defaults unless explicitly overridden.",
    )
    parser.add_argument(
        "-o", "--output", default=str(DEFAULT_OUTPUT_DIR / DEFAULT_IMAGE_NAME), help="Final output image path"
    )
    parser.add_argument("-s", "--image-size", default="16G", help="Minimum image size used for the build, e.g. 16G")
    parser.add_argument(
        "--branch", default="latest-stable", help="Distro branch/release/channel. Use 'distros' to list choices."
    )
    parser.add_argument("--release", default=None, help="Alias for --branch when selecting distro releases/channels")
    parser.add_argument("--nixos-channel", default=None, help="Alias for --branch when --distro nixos")
    parser.add_argument(
        "--arch", default="x86_64", choices=sorted({a for p in DISTROS.values() for a in p.arch_choices})
    )
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
    parser.add_argument("--bootloader", default="grub", choices=["grub", "systemd-boot", "extlinux"])
    parser.add_argument("--kernel", default="lts", choices=["lts", "stable", "generic", "huge"])
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
        description=f"{APP_TITLE}: {APP_DESCRIPTION} (TUI + CLI commands).",
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
        help="Search official distro packages and show top suggestions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    search.add_argument("query")
    search.add_argument("--distro", default="alpine", choices=distro_choices(include_aliases=True))
    search.add_argument("--branch", default="latest-stable")
    search.add_argument("--release", default=None)
    search.add_argument("--nixos-channel", default=None)
    search.add_argument(
        "--arch", default="x86_64", choices=sorted({a for p in DISTROS.values() for a in p.arch_choices})
    )
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    distros = sub.add_parser("distros", help="List supported Linux distributions and branch/release choices")
    distros.set_defaults(func=cmd_distros)

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
    apply_distro_defaults(args, argv)
    apply_profile_defaults(args, argv)
    if args.command != "tui":
        print(c(f"\n{APP_TITLE} — {APP_DESCRIPTION}", C.bold + C.cyan))
        print(c("─" * (len(APP_TITLE) + len(APP_DESCRIPTION) + 3), C.cyan), flush=True)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        warn("Interrupted.")
        return 130


if __name__ == "__main__":
    print(f"cli.py is import-only. Run ./{TERMINAL_ENTRYPOINT} (or ./{TERMINAL_ENTRYPOINT} tui).", file=sys.stderr)
    raise SystemExit(2)
