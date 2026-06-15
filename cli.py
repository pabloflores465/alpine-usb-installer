from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

APP_TITLE = "Alpine USB Installer"
DEFAULT_IMAGE_NAME = "alpine-usb.img"
APK_MIRROR = "https://dl-cdn.alpinelinux.org/alpine"
APK_SEARCH_REPOS = ("main", "community")
VALID_WMS = ("i3", "sway", "hyprland", "awesome", "bspwm", "openbox", "labwc")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
BRANCH_RE = re.compile(r"^(latest-stable|edge|v[0-9]+\.[0-9]+)$")

TERMINAL_ENTRYPOINT = "alpine-usb"
SOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
_TERMINAL_RUNTIME_DIR: Path | None = None
TERMINAL_RUNTIME_RESOURCES = (
    "build-alpine-usb.sh",
    "configure-alpine-usb.sh",
    "README.md",
    "LICENSE",
    "efi-fallback",
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


def format_size_bytes(size: int | None) -> str:
    if not size:
        return "unknown size"
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1000 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1000
    return f"{int(value)} B"


def validate_branch(branch: str) -> str:
    if not BRANCH_RE.match(branch):
        raise ValueError("Alpine branch must be latest-stable, edge, or v<major>.<minor> (for example v3.22)")
    return branch


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def parse_apkindex(text: str, repo: str) -> list[dict[str, str]]:
    packages = []
    current: dict[str, str] = {}
    for line in text.splitlines() + [""]:
        if not line:
            name = current.get("P")
            if name:
                packages.append({
                    "name": name,
                    "description": current.get("T", ""),
                    "version": current.get("V", ""),
                    "repo": repo,
                })
            current = {}
            continue
        if len(line) > 2 and line[1] == ":":
            current[line[0]] = line[2:]
    return packages


def fetch_official_apk_packages(branch: str, arch: str) -> list[dict[str, str]]:
    branch = validate_branch(branch)
    merged: dict[str, dict[str, str]] = {}
    for repo in APK_SEARCH_REPOS:
        url = f"{APK_MIRROR}/{branch}/{repo}/{arch}/APKINDEX.tar.gz"
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = next((m for m in tar.getmembers() if m.name.endswith("APKINDEX")), None)
            if member is None:
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            text = fh.read().decode("utf-8", errors="replace")
        for package in parse_apkindex(text, repo):
            merged.setdefault(package["name"], package)
    return sorted(merged.values(), key=lambda item: item["name"])


def search_official_apk_packages(branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_official_apk_packages(branch, arch):
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        haystack = f"{name} {desc}"
        if not all(term in haystack for term in terms):
            continue
        if name == query:
            score = 0
        elif name.startswith(query):
            score = 1
        elif all(term in name for term in terms):
            score = 2
        else:
            score = 3
        results.append((score, len(name), package["name"], package))
    results.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in results[:limit]]


def linux_lsblk_devices(path: str | None = None) -> list[dict]:
    cmd = ["lsblk", "-J", "-b", "-o", "PATH,NAME,SIZE,TRAN,TYPE,MODEL,SERIAL,RM,HOTPLUG"]
    if path:
        cmd.append(path)
    cp = run(cmd, capture_output=True)
    if cp.returncode != 0:
        return []
    try:
        return json.loads(cp.stdout).get("blockdevices", []) or []
    except Exception:
        return []


def linux_device_is_removable_disk(info: dict) -> bool:
    return (
        info.get("type") == "disk"
        and (str(info.get("rm", "0")) == "1" or str(info.get("hotplug", "0")) == "1" or info.get("tran") == "usb")
    )


def normalize_disk_device(dev: str) -> str:
    if platform.system() == "Darwin" and dev.startswith("/dev/rdisk"):
        return dev.replace("/dev/rdisk", "/dev/disk", 1)
    return dev


def device_safety_report(dev: str) -> tuple[bool, str, list[tuple[str, str]], str | None]:
    sysname = platform.system()
    dev = normalize_disk_device(dev)
    rows: list[tuple[str, str]] = [("Target", dev)]
    if looks_like_partition(dev):
        return False, dev, rows, f"Use the whole disk, not a partition: {dev}"
    if sysname == "Darwin":
        if not re.match(r"^/dev/disk\d+$", dev):
            return False, dev, rows, "macOS target must be a whole disk like /dev/disk7"
        cp = run(["diskutil", "info", "-plist", dev], capture_output=True)
        if cp.returncode != 0:
            return False, dev, rows, f"Could not inspect target device: {dev}"
        try:
            meta = plistlib.loads(cp.stdout.encode())
        except Exception as exc:
            return False, dev, rows, f"Could not parse diskutil info for {dev}: {exc}"
        if bool(meta.get("Internal")):
            return False, dev, rows, f"Refusing to flash internal disk: {dev}"
        size = format_size_bytes(int(meta.get("TotalSize", 0) or 0))
        model = meta.get("MediaName") or meta.get("IORegistryEntryName") or "unknown"
        protocol = meta.get("BusProtocol") or meta.get("DeviceProtocol") or "unknown"
        serial = meta.get("DeviceIdentifier") or "unknown"
        rows.extend([("Model/media", str(model)), ("Size", size), ("Protocol", str(protocol)), ("Serial/id", str(serial))])
        return True, dev, rows, None
    if sysname == "Linux":
        infos = linux_lsblk_devices(dev)
        if not infos:
            return False, dev, rows, f"Could not inspect target device with lsblk: {dev}"
        info = infos[0]
        if not linux_device_is_removable_disk(info):
            return False, dev, rows, f"Refusing non-removable/non-hotplug disk: {dev}"
        rows.extend([
            ("Model", str(info.get("model") or "unknown")),
            ("Size", format_size_bytes(int(info.get("size", 0) or 0))),
            ("Transport", str(info.get("tran") or "unknown")),
            ("Serial", str(info.get("serial") or "unknown")),
            ("RM/HOTPLUG", f"{info.get('rm', 0)}/{info.get('hotplug', 0)}"),
        ])
        return True, dev, rows, None
    return False, dev, rows, "Windows flashing is not implemented. Use Rufus/balenaEtcher with the generated image."


def list_devices() -> list[tuple[str, str]]:
    sysname = platform.system()
    devices: list[tuple[str, str]] = []
    if sysname == "Darwin":
        cp = run(["diskutil", "list", "-plist", "external", "physical"], capture_output=True)
        try:
            data = plistlib.loads(cp.stdout.encode())
            for disk in data.get("AllDisksAndPartitions", []):
                ident = disk.get("DeviceIdentifier")
                if not ident:
                    continue
                dev = f"/dev/{ident}"
                ok_safe, safe_dev, rows, _reason = device_safety_report(dev)
                if not ok_safe:
                    continue
                details = {key: value for key, value in rows}
                label = f"{safe_dev} ({details.get('Size', 'unknown size')}) {details.get('Model/media', 'USB')} serial={details.get('Serial/id', 'unknown')}"
                devices.append((safe_dev, label))
        except Exception:
            pass
    elif sysname == "Linux":
        for info in linux_lsblk_devices():
            if not linux_device_is_removable_disk(info):
                continue
            path = info.get("path") or (f"/dev/{info.get('name')}" if info.get("name") else "")
            if not path:
                continue
            size = format_size_bytes(int(info.get("size", 0) or 0))
            model = str(info.get("model") or "USB")
            serial = str(info.get("serial") or "unknown")
            devices.append((path, f"{path} ({size}) {model} serial={serial}".strip()))
    return devices


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


def env_from_build_args(args: argparse.Namespace) -> dict[str, str]:
    validate_branch(args.branch)
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

    return {
        "IMAGE_NAME": f".alpine-usb-cli-{os.getpid()}.img",
        "IMAGE_SIZE": args.image_size,
        "ALPINE_BRANCH": args.branch,
        "ARCH": args.arch,
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
        "ALPINE_USB_BOOTLOADER": args.bootloader,
        "ALPINE_USB_KERNEL_FLAVOR": args.kernel,
        "ALPINE_USB_BOOT_TIMEOUT": str(args.boot_timeout),
        "ALPINE_USB_SYSTEMD_BOOT_CONSOLE_MODE": args.systemd_boot_console_mode,
        "ALPINE_USB_AUTO_RESIZE": bool_env(args.auto_resize),
        "ALPINE_USB_EXTRA_PACKAGES": split_packages(args.extra_package, args.extra_packages),
    }


def print_build_summary(env: dict[str, str], output: Path):
    rows = [
        ("Output", str(output)),
        ("Minimum image size", env["IMAGE_SIZE"]),
        ("Alpine", f"{env['ALPINE_BRANCH']} / {env['ARCH']}"),
        ("Desktop", env["ALPINE_USB_DESKTOP"]),
        ("Window managers", env["ALPINE_USB_TILING_WMS"] or "none"),
        ("Default session", env["ALPINE_USB_DEFAULT_SESSION"]),
        ("Display manager", env["ALPINE_USB_DISPLAY_MANAGER"]),
        ("Network", f"{env['ALPINE_USB_NETWORK']} wifi={env['ALPINE_USB_WIFI']} bluetooth={env['ALPINE_USB_BLUETOOTH']}"),
        ("Audio / browser", f"{env['ALPINE_USB_AUDIO']} / {env['ALPINE_USB_BROWSER']}"),
        ("Boot", f"{env['ALPINE_USB_BOOTLOADER']} linux-{env['ALPINE_USB_KERNEL_FLAVOR']} firmware={env['ALPINE_USB_FIRMWARE']}"),
        ("Auto-resize USB", env["ALPINE_USB_AUTO_RESIZE"]),
        ("Keyboard", f"console={env['ALPINE_USB_CONSOLE_KEYMAP']} xkb={env['ALPINE_USB_XKB_LAYOUT']}"),
        ("Extra packages", env["ALPINE_USB_EXTRA_PACKAGES"] or "none"),
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
}


def prepare_secret_env(env: dict[str, str]) -> tuple[dict[str, str], list[Path]]:
    safe_env = dict(env)
    created: list[Path] = []
    secret_dir = repo_root() / ".work" / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.chmod(0o700)
    for key, file_key in SECRET_ENV_TO_FILE.items():
        value = safe_env.pop(key, "")
        path = secret_dir / f"{key.lower()}-{os.getpid()}.secret"
        path.write_text(value)
        path.chmod(0o600)
        safe_env[file_key] = str(path)
        created.append(path)
    return safe_env, created


def cleanup_secret_files(paths: list[Path]):
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def run_config_dry_run(env: dict[str, str]) -> int:
    sys.stdout.flush()
    dry_env = os.environ.copy()
    safe_env, secret_files = prepare_secret_env(env)
    dry_env.update(safe_env)
    dry_env["ALPINE_USB_DRY_RUN"] = "1"
    dry_env.pop("IMAGE_NAME", None)
    try:
        proc = subprocess.Popen(["./configure-alpine-usb.sh"], cwd=repo_root(), env=dry_env)
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
        info("Dry-run only: validating generated Alpine configuration and package list.")
        return run_config_dry_run(env)

    if output.exists() and not confirm(f"Overwrite existing image {output}?", args.yes):
        warn("Cancelled.")
        return 1
    if not confirm("Build this Alpine USB image now?", args.yes):
        warn("Cancelled.")
        return 1

    build_env = os.environ.copy()
    safe_env, secret_files = prepare_secret_env(env)
    build_env.update(safe_env)
    build_name = env["IMAGE_NAME"]
    built_path = repo_root() / build_name
    try:
        if built_path.exists():
            built_path.unlink()
        info("Starting build. This can take a while…")
        sys.stdout.flush()
        proc = subprocess.Popen(["./build-alpine-usb.sh"], cwd=repo_root(), env=build_env)
        code = proc.wait()
        if code != 0:
            err(f"Build failed with exit code {code}")
            return code
        if not built_path.exists():
            err(f"Build finished but expected image was not found: {built_path}")
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        shutil.move(str(built_path), str(output))
        ok(f"Image ready: {output}")
        return 0
    finally:
        cleanup_secret_files(secret_files)
        if built_path.exists() and built_path != output:
            try:
                built_path.unlink()
            except OSError:
                pass


def cmd_search(args: argparse.Namespace) -> int:
    try:
        validate_branch(args.branch)
    except ValueError as exc:
        err(str(exc))
        return 2
    info(f"Searching Alpine {args.branch}/{args.arch} official repos: {', '.join(APK_SEARCH_REPOS)}")
    try:
        results = search_official_apk_packages(args.branch, args.arch, args.query, args.limit)
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


def selected_device(label: str) -> str | None:
    if label.startswith("/dev/"):
        return label.split()[0]
    match = re.match(r"(/dev/\S+)", label)
    return match.group(1) if match else None


def looks_like_partition(dev: str) -> bool:
    return bool(re.match(r"^/dev/(r?disk\d+s\d+|sd[a-z]\d+|nvme\d+n\d+p\d+|mmcblk\d+p\d+)", dev))


def cmd_flash(args: argparse.Namespace) -> int:
    image = Path(args.image).expanduser().resolve()
    dev = selected_device(args.device)
    if not image.exists():
        err(f"Image not found: {image}")
        return 1
    if not dev:
        err("Invalid target device.")
        return 1
    ok_safe, dev, device_rows, reason = device_safety_report(dev)
    if not ok_safe:
        err(reason or "Unsafe target device.")
        return 1

    print_panel("Flash USB", [("Image", str(image)), ("Image size", f"{image.stat().st_size / 1_000_000_000:.1f} GB"), *device_rows])
    if not args.yes:
        warn("This permanently erases the selected USB device.")
        typed = input(f"Type {c(f'ERASE {dev}', C.red)} to continue: ").strip()
        if typed != f"ERASE {dev}":
            warn("Cancelled.")
            return 1

    sysname = platform.system()
    if sysname == "Darwin":
        raw = dev.replace("/dev/disk", "/dev/rdisk")
        cmd = ["sudo", "dd", f"if={image}", f"of={raw}", "bs=4m", "status=progress"]
        subprocess.run(["diskutil", "unmountDisk", dev])
        code = subprocess.call(cmd)
        subprocess.run(["sync"])
        subprocess.run(["diskutil", "eject", dev])
        return code
    if sysname == "Linux":
        cmd = ["dd", f"if={image}", f"of={dev}", "bs=4M", "status=progress", "conv=fsync"]
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
            checks.append(("docker running", run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0))
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
    parser.add_argument("-o", "--output", default=str(Path(tempfile.gettempdir()) / "alpine-usb-installer" / DEFAULT_IMAGE_NAME), help="Final output image path")
    parser.add_argument("-s", "--image-size", default="16G", help="Minimum image size used for the build, e.g. 16G")
    parser.add_argument("--branch", default="latest-stable", help="Alpine branch: latest-stable, edge, v3.22, ...")
    parser.add_argument("--arch", default="x86_64", choices=["x86_64"], help="Target architecture")
    parser.add_argument("--hostname", default="alpine-usb")
    parser.add_argument("--user", default="alpine")
    parser.add_argument("--password", default=None, help="Initial user password (use --ask-password to avoid shell history)")
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
    parser.add_argument("--display-manager", default="auto", choices=["auto", "lightdm", "sddm", "gdm", "lxdm", "greetd", "none"])
    parser.add_argument("--default-session", default="auto", choices=["auto", "xfce", "gnome", "plasma", "mate", "lxqt", *VALID_WMS, "shell"])
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
    parser.add_argument("--boot-timeout", type=int, default=3)
    parser.add_argument("--systemd-boot-console-mode", default="max", help="systemd-boot console-mode: max, auto, keep or numeric mode")
    parser.add_argument("--auto-resize", dest="auto_resize", action="store_true", default=True)
    parser.add_argument("--no-auto-resize", dest="auto_resize", action="store_false")
    parser.add_argument("--extra-package", action="append", help="Extra APK package; can be repeated or contain spaces")
    parser.add_argument("--extra-packages", default="", help="Space-separated extra APK packages")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print generated package list without building")
    parser.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Unified terminal interface for Alpine USB images (TUI + CLI commands).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a configurable Alpine USB image", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    add_common_build_options(build)
    build.set_defaults(func=cmd_build)

    search = sub.add_parser("search", help="Search official Alpine packages and show top suggestions", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    search.add_argument("query")
    search.add_argument("--branch", default="latest-stable")
    search.add_argument("--arch", default="x86_64")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    devices = sub.add_parser("devices", help="List removable USB devices")
    devices.set_defaults(func=cmd_devices)

    flash = sub.add_parser("flash", help="Flash an image to a USB device", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
