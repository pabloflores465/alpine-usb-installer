from __future__ import annotations

ALPINE_MIRROR = "https://dl-cdn.alpinelinux.org/alpine"
ARCH_PACKAGE_SEARCH_URL = "https://archlinux.org/packages/search/json/"
SLACKWARE_MIRROR = "https://mirrors.slackware.com/slackware"
VOID_REPOSITORIES = {
    "current": "https://repo-default.voidlinux.org/current",
    "glibc": "https://repo-default.voidlinux.org/current",
}
OPENSUSE_TUMBLEWEED_OSS_URL = "https://download.opensuse.org/tumbleweed/repo/oss"
OPENSUSE_LEAP_OSS_BASE_URL = "https://download.opensuse.org/distribution/leap"


def opensuse_oss_repo_url(version: str) -> str:
    return f"{OPENSUSE_LEAP_OSS_BASE_URL}/{version}/repo/oss"
