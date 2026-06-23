from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from ledit_core.nixos.config import NixosBuildConfig, generate_configuration_nix, generate_flake_nix

LogFunc = Callable[[str], None]


def _log(log: LogFunc | None, message: str) -> None:
    (log or print)(message)


def _run_streaming(cmd: list[str], *, cwd: Path | None = None, log: LogFunc | None = None) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in proc.stdout or []:
        _log(log, line.rstrip())
    return proc.wait()


def env_to_config(env: dict[str, str]) -> NixosBuildConfig:
    def enabled(key: str, default: str = "1") -> bool:
        return env.get(key, default).strip().lower() in {"1", "yes", "true", "on", "enabled"}

    wms = tuple(part for part in env.get("NIXOS_USB_TILING_WMS", "").replace(",", " ").split() if part)
    extra = tuple(part for part in env.get("NIXOS_USB_EXTRA_PACKAGES", "").split() if part)
    channel = env.get("NIXOS_CHANNEL") or "nixos-24.11"
    arch = env.get("ARCH", "x86_64-linux")
    if arch == "x86_64":
        arch = "x86_64-linux"
    return NixosBuildConfig(
        channel=channel,
        arch=arch,
        hostname=env.get("NIXOS_USB_HOSTNAME", "ledit-nixos"),
        user=env.get("NIXOS_USB_USER", "nixos"),
        password=env.get("NIXOS_USB_PASSWORD", ""),
        root_password=env.get("NIXOS_USB_ROOT_PASSWORD") or env.get("NIXOS_USB_PASSWORD", ""),
        timezone=env.get("NIXOS_USB_TIMEZONE", "UTC"),
        locale=env.get("NIXOS_USB_LOCALE", "en_US.UTF-8"),
        console_keymap=env.get("NIXOS_USB_CONSOLE_KEYMAP", "us"),
        xkb_layout=env.get("NIXOS_USB_XKB_LAYOUT", "us"),
        xkb_variant=env.get("NIXOS_USB_XKB_VARIANT", ""),
        xkb_model=env.get("NIXOS_USB_XKB_MODEL", "pc105"),
        desktop=env.get("NIXOS_USB_DESKTOP", "xfce"),
        display_manager=env.get("NIXOS_USB_DISPLAY_MANAGER", "auto"),
        default_session=env.get("NIXOS_USB_DEFAULT_SESSION", "auto"),
        window_managers=wms,
        browser=env.get("NIXOS_USB_BROWSER", "firefox"),
        audio=env.get("NIXOS_USB_AUDIO", "pipewire"),
        network=env.get("NIXOS_USB_NETWORK", "networkmanager"),
        wifi=enabled("NIXOS_USB_WIFI"),
        bluetooth=enabled("NIXOS_USB_BLUETOOTH"),
        bootloader=env.get("NIXOS_USB_BOOTLOADER", "extlinux"),
        kernel=env.get("NIXOS_USB_KERNEL_FLAVOR", "lts"),
        firmware=env.get("NIXOS_USB_FIRMWARE", "full"),
        auto_resize=enabled("NIXOS_USB_AUTO_RESIZE"),
        extra_packages=extra,
    )


def summary_rows(config: NixosBuildConfig, output: Path) -> list[tuple[str, str]]:
    return [
        ("Output", str(output)),
        ("NixOS", f"{config.channel} / {config.arch}"),
        ("Desktop", config.desktop),
        ("Window managers", " ".join(config.window_managers) or "none"),
        ("Default session", config.default_session),
        ("Display manager", config.display_manager),
        ("Network", f"{config.network} wifi={int(config.wifi)} bluetooth={int(config.bluetooth)}"),
        ("Audio / browser", f"{config.audio} / {config.browser}"),
        ("Boot", f"{config.bootloader} linux-{config.kernel} firmware={config.firmware}"),
        ("Auto-resize USB", str(int(config.auto_resize))),
        ("Keyboard", f"console={config.console_keymap} xkb={config.xkb_layout}"),
        ("Extra packages", " ".join(config.extra_packages) or "none"),
    ]


def run_nixos_dry_run(config: NixosBuildConfig, *, log: LogFunc | None = None) -> int:
    _log(log, "Dry-run only: generated NixOS flake and configuration follow.")
    _log(log, "--- flake.nix ---")
    for line in generate_flake_nix(config).rstrip().splitlines():
        _log(log, line)
    _log(log, "--- configuration.nix ---")
    for line in generate_configuration_nix(config).rstrip().splitlines():
        _log(log, line)
    _log(log, "DRY RUN OK: NixOS configuration rendered successfully. Build requires nixos-generate or Docker.")
    return 0


def effective_nixos_image_config(config: NixosBuildConfig, *, log: LogFunc | None = None) -> NixosBuildConfig:
    if config.bootloader == "extlinux":
        return config
    _log(log, "NixOS sd-image builds use extlinux; overriding selected bootloader for image compile.")
    return replace(config, bootloader="extlinux")


def run_nixos_docker_build(config: NixosBuildConfig, output: Path, *, log: LogFunc | None = None) -> int:
    docker = shutil.which("docker")
    if docker is None:
        _log(log, "NixOS Docker build requires Docker on PATH.")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nixos-build-", dir=output.parent) as tmp:
        work = Path(tmp)
        (work / "configuration.nix").write_text(generate_configuration_nix(config))
        (work / "flake.nix").write_text(generate_flake_nix(config))
        script = f"""
          nix --extra-experimental-features 'nix-command flakes' --option filter-syscalls false build \
            .#nixosConfigurations.usb.config.system.build.sdImage --no-write-lock-file --out-link result
          artifact=$(find -L result -maxdepth 4 -type f \\( -name '*.img' -o -name '*.raw' -o -name '*.img.zst' -o -name '*.raw.zst' \\) | sort | head -n 1)
          if [ -z "$artifact" ]; then
            echo 'No NixOS image artifact found under result' >&2
            exit 1
          fi
          rm -f /work/nixos-output.img /work/nixos-output.img.zst
          case "$artifact" in
            *.zst)
              cp "$artifact" /work/nixos-output.img.zst
              nix --extra-experimental-features 'nix-command flakes' shell github:NixOS/nixpkgs/{config.channel}#zstd \
                -c zstd -df /work/nixos-output.img.zst -o /work/nixos-output.img
              ;;
            *)
              cp "$artifact" /work/nixos-output.img
              ;;
          esac
          chmod 0644 /work/nixos-output.img 2>/dev/null || true
        """
        cmd = [
            docker,
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--security-opt",
            "seccomp=unconfined",
            "-v",
            f"{work}:/work",
            "-w",
            "/work",
            "nixos/nix:latest",
            "sh",
            "-ceu",
            script,
        ]
        _log(log, "Starting NixOS Docker sd-image build. This can take a while…")
        code = _run_streaming(cmd, log=log)
        if code != 0:
            _log(log, f"NixOS Docker build failed with exit code {code}")
            return code
        image = work / "nixos-output.img"
        if not image.is_file():
            _log(log, "NixOS Docker build finished but no image was copied out")
            return 1
        shutil.copy2(image, output)
    _log(log, f"NixOS image written: {output}")
    return 0


def run_nixos_build(config: NixosBuildConfig, output: Path, *, log: LogFunc | None = None) -> int:
    config = effective_nixos_image_config(config, log=log)
    if platform.system() == "Darwin":
        return run_nixos_docker_build(config, output, log=log)
    tool = shutil.which("nixos-generate")
    if tool is None:
        if shutil.which("docker") is not None:
            _log(log, "nixos-generate not found; falling back to Docker sd-image build.")
            return run_nixos_docker_build(config, output, log=log)
        _log(log, "NixOS build requires nixos-generate or Docker. Install nixpkgs#nixos-generators or Docker.")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ledit-nixos-") as tmp:
        work = Path(tmp)
        (work / "configuration.nix").write_text(generate_configuration_nix(config))
        (work / "flake.nix").write_text(generate_flake_nix(config))
        out_link = work / "result"
        cmd = [tool, "--flake", f"{work}#usb", "--format", "raw", "--out-link", str(out_link)]
        _log(log, "Starting NixOS image build with nixos-generate. This can take a while…")
        code = _run_streaming(cmd, log=log)
        if code != 0:
            _log(log, f"NixOS build failed with exit code {code}")
            return code
        candidates = [
            out_link,
            *out_link.glob("*.img"),
            *out_link.glob("*.raw"),
            *out_link.glob("**/*.img"),
            *out_link.glob("**/*.raw"),
        ]
        image = next((candidate for candidate in candidates if candidate.is_file()), None)
        if image is None:
            _log(log, f"Build finished but no raw image was found under {out_link}")
            return 1
        shutil.copy2(image, output)
    _log(log, f"NixOS image written: {output}")
    return 0
