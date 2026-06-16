from __future__ import annotations

VALID_WMS = ("i3", "sway", "hyprland", "awesome", "bspwm", "openbox", "labwc")

BUILD_PROFILE_DEFAULTS: dict[str, dict[str, object]] = {
    "minimal": {
        "desktop": "none",
        "display_manager": "none",
        "browser": "none",
        "audio": "none",
        "network": "none",
        "wifi": False,
        "bluetooth": False,
        "firmware": "none",
        "legacy_x11_drivers": False,
    }
}

BUILD_PROFILE_OPTIONS = {
    "desktop": ("--desktop",),
    "display_manager": ("--display-manager",),
    "browser": ("--browser",),
    "audio": ("--audio",),
    "network": ("--network",),
    "wifi": ("--wifi", "--no-wifi"),
    "bluetooth": ("--bluetooth", "--no-bluetooth"),
    "firmware": ("--firmware",),
    "legacy_x11_drivers": ("--legacy-x11-drivers", "--no-legacy-x11-drivers"),
}


def option_was_passed(argv: list[str], names: tuple[str, ...]) -> bool:
    return any(token == name or token.startswith(name + "=") for token in argv for name in names)


def apply_profile_defaults(args: object, argv: list[str]) -> None:
    if getattr(args, "command", None) != "build":
        return
    defaults = BUILD_PROFILE_DEFAULTS.get(getattr(args, "profile", "compatibility"), {})
    for attr, value in defaults.items():
        if not option_was_passed(argv, BUILD_PROFILE_OPTIONS[attr]):
            setattr(args, attr, value)
