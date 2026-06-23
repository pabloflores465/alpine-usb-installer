from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

NIXOS_DEFAULT_CHANNEL = "nixos-24.11"
NIXOS_STABLE_CHANNELS = ("nixos-24.11", "nixos-25.05", "nixos-unstable")
_NIX_ATTR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]*$")


def validate_nix_channel(channel: str) -> None:
    if channel not in NIXOS_STABLE_CHANNELS:
        allowed = ", ".join(NIXOS_STABLE_CHANNELS)
        raise ValueError(f"Unsupported NixOS channel '{channel}'. Expected one of: {allowed}")


def validate_nix_package_name(name: str) -> None:
    if not _NIX_ATTR_RE.match(name):
        raise ValueError(f"Invalid Nix package attribute: {name!r}")


def _cache_path(cache_dir: Path, channel: str, query: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", query).strip("_") or "query"
    return cache_dir / f"nix-search-{channel}-{safe}.json"


def _normalise_search_results(raw: dict[str, Any], limit: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for attr, meta in raw.items():
        attr_name = attr.removeprefix("legacyPackages.x86_64-linux.").removeprefix("packages.x86_64-linux.")
        package = meta.get("pname") or attr_name.rsplit(".", 1)[-1]
        results.append(
            {
                "name": attr_name,
                "package": str(package),
                "version": str(meta.get("version") or ""),
                "description": str(meta.get("description") or meta.get("meta", {}).get("description") or ""),
                "repo": "nixpkgs",
            }
        )
    return results[:limit]


def search_nix_packages(
    channel: str,
    query: str,
    limit: int = 10,
    *,
    cache_dir: Path | None = None,
    timeout: int = 45,
) -> list[dict[str, str]]:
    """Search nixpkgs with a small JSON cache.

    This is intentionally adapter-thin: it shells out to `nix search --json` when available
    and stores successful responses under `.work` (or the provided cache directory).
    """
    validate_nix_channel(channel)
    if not query.strip():
        raise ValueError("Search query is required")
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = _cache_path(cache_dir, channel, query)
        if cached.exists():
            return _normalise_search_results(json.loads(cached.read_text()), limit)
    flake_ref = f"github:NixOS/nixpkgs/{channel}"
    proc = subprocess.run(
        ["nix", "search", "--json", flake_ref, query],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "nix search failed")
    raw = json.loads(proc.stdout or "{}")
    if cache_dir is not None:
        cached.write_text(json.dumps(raw, indent=2, sort_keys=True))
    return _normalise_search_results(raw, limit)
