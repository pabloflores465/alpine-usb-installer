from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DistroProvider:
    id: str
    name: str
    default_release: str
    branch_option: str
    default_hostname: str
    default_user: str
    default_output_name: str
    build_script: str
    configure_script: str
    env_prefix: str
    release_help: str
    package_noun: str


ALPINE = DistroProvider(
    id="alpine",
    name="Alpine Linux",
    default_release="latest-stable",
    branch_option="branch",
    default_hostname="alpine-usb",
    default_user="alpine",
    default_output_name="alpine-usb.img",
    build_script="./build-alpine-usb.sh",
    configure_script="./configure-alpine-usb.sh",
    env_prefix="ALPINE_USB",
    release_help="Alpine branch: latest-stable, edge, v3.22, ...",
    package_noun="APK",
)

UBUNTU = DistroProvider(
    id="ubuntu",
    name="Ubuntu",
    default_release="24.04",
    branch_option="release",
    default_hostname="ubuntu-usb",
    default_user="ubuntu",
    default_output_name="ubuntu-usb.img",
    build_script="./build-ubuntu-usb.sh",
    configure_script="./configure-ubuntu-usb.sh",
    env_prefix="UBUNTU_USB",
    release_help="Ubuntu release/codename: 24.04, noble, 22.04, jammy",
    package_noun="APT",
)

SUPPORTED_DISTROS: dict[str, DistroProvider] = {"alpine": ALPINE, "ubuntu": UBUNTU}


def get_provider(distro: str) -> DistroProvider:
    try:
        return SUPPORTED_DISTROS[distro.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported distro: {distro}") from exc
