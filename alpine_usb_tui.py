#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import getpass
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import alpine_usb_cli as cli

CHOICES = {
    "image_size": ["8G", "16G", "24G", "32G", "64G", "128G"],
    "branch": ["latest-stable", "edge", "v3.22", "v3.21"],
    "arch": ["x86_64"],
    "timezone": ["UTC", "America/Mexico_City", "America/Bogota", "America/Lima", "America/Santiago", "Europe/Madrid"],
    "locale": ["en_US.UTF-8", "es_ES.UTF-8", "es_MX.UTF-8"],
    "console_keymap": ["la-latin1", "es", "us", "br-abnt2", "fr", "de"],
    "xkb_layout": ["latam", "es", "us", "br", "fr", "de"],
    "desktop": ["xfce", "gnome", "plasma", "mate", "lxqt", "none"],
    "display_manager": ["auto", "lightdm", "sddm", "gdm", "lxdm", "greetd", "none"],
    "default_session": ["auto", "xfce", "gnome", "plasma", "mate", "lxqt", "i3", "sway", "hyprland", "awesome", "bspwm", "openbox", "labwc", "shell"],
    "browser": ["firefox-esr", "firefox", "chromium", "none"],
    "audio": ["pipewire", "alsa", "none"],
    "network": ["networkmanager", "none"],
    "bootloader": ["grub", "systemd-boot"],
    "kernel": ["lts", "stable"],
    "firmware": ["full", "none"],
    "systemd_boot_console_mode": ["max", "auto", "keep", "0", "1", "2", "3"],
}

WM_CHOICES = list(cli.VALID_WMS)

DEFAULT_CONFIG = {
    "output": str(cli.repo_root() / cli.DEFAULT_IMAGE_NAME),
    "image_size": "16G",
    "branch": "latest-stable",
    "arch": "x86_64",
    "hostname": "alpine-usb",
    "user": "pablo",
    "password": "pablo",
    "root_password": "pablo",
    "timezone": "UTC",
    "locale": "en_US.UTF-8",
    "language": "",
    "console_keymap": "la-latin1",
    "xkb_layout": "latam",
    "xkb_variant": "",
    "xkb_model": "pc105",
    "desktop": "xfce",
    "display_manager": "auto",
    "default_session": "auto",
    "wms": [],
    "browser": "firefox-esr",
    "audio": "pipewire",
    "network": "networkmanager",
    "wifi": True,
    "bluetooth": True,
    "bootloader": "grub",
    "kernel": "lts",
    "firmware": "full",
    "boot_timeout": "3",
    "systemd_boot_console_mode": "max",
    "auto_resize": True,
    "extra_packages": "",
    "device": "",
}


class TuiExit(Exception):
    pass


class TuiApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.config = dict(DEFAULT_CONFIG)
        self.config["wms"] = []
        self.status = "Ready. Use ↑/↓, Enter, q."
        self.last_devices: list[tuple[str, str]] = []
        self._init_curses()

    def _init_curses(self):
        curses.curs_set(0)
        curses.use_default_colors()
        curses.start_color()
        self.has_colors = curses.has_colors()
        if self.has_colors:
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(7, curses.COLOR_MAGENTA, -1)
        self.stdscr.keypad(True)

    def color(self, pair: int, bold: bool = False):
        attr = curses.color_pair(pair) if self.has_colors else 0
        if bold:
            attr |= curses.A_BOLD
        return attr

    def clear(self):
        self.stdscr.erase()

    def safe_addnstr(self, y: int, x: int, text: str, width: int, attr: int = 0):
        h, w = self.stdscr.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w or width <= 0:
            return
        # Some curses implementations (notably macOS ncurses through Python)
        # return ERR when writing into the bottom-right cell. Keep one column
        # free on the last line to avoid crashing the TUI.
        max_width = min(width, w - x)
        if y == h - 1:
            max_width = max(0, max_width - 1)
        if max_width <= 0:
            return
        try:
            self.stdscr.addnstr(y, x, text, max_width, attr)
        except curses.error:
            # Best-effort drawing: never let a terminal paint quirk kill the UI.
            pass

    def draw_header(self, title: str):
        _h, w = self.stdscr.getmaxyx()
        header = f" Alpine USB Installer TUI  ›  {title} "
        self.safe_addnstr(0, 0, header.ljust(w), w, self.color(5, True))
        subtitle = "Complete terminal UI: build, package search, USB devices and flashing"
        self.safe_addnstr(1, 2, subtitle, max(0, w - 4), self.color(1))

    def draw_footer(self):
        h, w = self.stdscr.getmaxyx()
        if h < 3 or w < 20:
            return
        help_text = " ↑/↓ move  Enter edit/select  Space toggle  b back  q quit "
        self.safe_addnstr(h - 2, 0, help_text.ljust(w), w, self.color(6))
        self.safe_addnstr(h - 1, 0, (" " + self.status).ljust(w), w, self.color(3))

    def truncate(self, text: str, width: int) -> str:
        if width <= 0:
            return ""
        return text if len(text) <= width else text[: max(0, width - 1)] + "…"

    def menu(self, title: str, items: list[tuple[str, str]], start_index: int = 0) -> int | None:
        index = max(0, min(start_index, len(items) - 1))
        top = 0
        while True:
            self.clear()
            self.draw_header(title)
            h, w = self.stdscr.getmaxyx()
            visible = max(1, h - 6)
            if index < top:
                top = index
            if index >= top + visible:
                top = index - visible + 1
            for row, (label, value) in enumerate(items[top: top + visible], start=3):
                item_index = top + row - 3
                selected = item_index == index
                marker = "➜" if selected else " "
                left = f"{marker} {label}"
                right = value
                attr = self.color(6, True) if selected else curses.A_NORMAL
                self.stdscr.addnstr(row, 2, self.truncate(left, max(10, w // 2 - 4)), max(0, w // 2 - 4), attr)
                self.stdscr.addnstr(row, max(4, w // 2), self.truncate(right, max(0, w // 2 - 3)), max(0, w // 2 - 3), attr)
            self.draw_footer()
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in (ord("q"), 27):
                raise TuiExit
            if key in (ord("b"), curses.KEY_BACKSPACE):
                return None
            if key in (curses.KEY_UP, ord("k")):
                index = (index - 1) % len(items)
            elif key in (curses.KEY_DOWN, ord("j")):
                index = (index + 1) % len(items)
            elif key in (curses.KEY_ENTER, 10, 13, ord(" ")):
                return index

    def prompt(self, title: str, current: str = "", secret: bool = False) -> str | None:
        self.clear()
        self.draw_header(title)
        h, w = self.stdscr.getmaxyx()
        self.stdscr.addnstr(4, 2, f"Current: {'*' * len(current) if secret else current}", w - 4)
        self.stdscr.addnstr(6, 2, "New value (empty keeps current, ESC cancels): ", w - 4, self.color(1))
        self.draw_footer()
        self.stdscr.refresh()
        curses.curs_set(1)
        if secret:
            curses.noecho()
        else:
            curses.echo()
        buf = []
        try:
            y, x = 6, min(w - 2, 47)
            while True:
                ch = self.stdscr.getch(y, x + len(buf))
                if ch == 27:
                    return None
                if ch in (10, 13):
                    value = "".join(buf)
                    return value if value else current
                if ch in (curses.KEY_BACKSPACE, 127, 8):
                    if buf:
                        buf.pop()
                        self.stdscr.addch(y, x + len(buf), " ")
                        self.stdscr.move(y, x + len(buf))
                    continue
                if 32 <= ch <= 126 and len(buf) < max(1, w - x - 2):
                    buf.append(chr(ch))
                    self.stdscr.addch(y, x + len(buf) - 1, "*" if secret else chr(ch))
        finally:
            curses.noecho()
            curses.curs_set(0)

    def choice(self, title: str, options: list[str], current: str) -> str:
        items = [(opt, "current" if opt == current else "") for opt in options]
        idx = options.index(current) if current in options else 0
        selected = self.menu(title, items, idx)
        return current if selected is None else options[selected]

    def edit_fields(self, title: str, fields: list[tuple[str, str, str]]):
        idx = 0
        while True:
            items = []
            for label, key, kind in fields:
                value = self.config[key]
                if kind == "bool":
                    text = "yes" if value else "no"
                elif kind == "password":
                    text = "•" * len(str(value))
                elif key == "wms":
                    text = ", ".join(value) if value else "none"
                else:
                    text = str(value) if str(value) else "(empty)"
                items.append((label, text))
            selected = self.menu(title, items, idx)
            if selected is None:
                return
            idx = selected
            label, key, kind = fields[selected]
            if kind == "bool":
                self.config[key] = not bool(self.config[key])
            elif kind == "choice":
                self.config[key] = self.choice(label, CHOICES[key], str(self.config[key]))
            elif kind == "multi_wm":
                self.edit_wms()
            else:
                new_value = self.prompt(label, str(self.config[key]), secret=(kind == "password"))
                if new_value is not None:
                    self.config[key] = new_value

    def edit_wms(self):
        selected = set(self.config["wms"])
        idx = 0
        while True:
            items = [(wm, "enabled" if wm in selected else "disabled") for wm in WM_CHOICES]
            choice = self.menu("Toggle optional window managers", items + [("Done", "return")], idx)
            if choice is None or choice == len(items):
                self.config["wms"] = [wm for wm in WM_CHOICES if wm in selected]
                return
            idx = choice
            wm = WM_CHOICES[choice]
            if wm in selected:
                selected.remove(wm)
            else:
                selected.add(wm)

    def extra_packages_screen(self):
        while True:
            items = [
                ("Current packages", self.config["extra_packages"] or "none"),
                ("Edit manually", "space-separated APK package names"),
                ("Search official Alpine packages", "top 10 suggestions from main + community"),
                ("Clear packages", "remove all extra packages"),
                ("Back", "return"),
            ]
            choice = self.menu("Extra APK packages", items)
            if choice is None or choice == 4:
                return
            if choice == 1:
                value = self.prompt("Extra APK packages", self.config["extra_packages"])
                if value is not None:
                    self.config["extra_packages"] = self.dedupe_packages(value)
            elif choice == 2:
                self.package_search_screen()
            elif choice == 3 and self.confirm_curses("Clear all extra packages?"):
                self.config["extra_packages"] = ""

    def dedupe_packages(self, text: str) -> str:
        result = []
        seen = set()
        for pkg in re.split(r"\s+", text.strip()):
            if pkg and pkg not in seen:
                seen.add(pkg)
                result.append(pkg)
        return " ".join(result)

    def package_search_screen(self):
        query = self.prompt("Search Alpine packages", "")
        if not query:
            return
        self.status = f"Searching official APK indexes for '{query}'…"
        self.draw_wait("Package search", self.status)
        try:
            results = cli.search_official_apk_packages(self.config["branch"], self.config["arch"], query, 10)
        except Exception as exc:
            self.message("Package search failed", str(exc), error=True)
            return
        if not results:
            self.message("Package search", f"No packages found for '{query}'.")
            return
        lines = []
        for i, pkg in enumerate(results, 1):
            desc = pkg.get("description") or "No description"
            lines.append(f"{i}. {pkg['name']}  [{pkg.get('repo', '?')}]  {desc}")
        lines.append("")
        lines.append("Type numbers to add, e.g. 1 3 5. Empty cancels.")
        answer = self.prompt_multiline("Top 10 suggestions", lines)
        if not answer:
            return
        chosen = []
        for token in re.split(r"[\s,]+", answer.strip()):
            if token.isdigit():
                n = int(token)
                if 1 <= n <= len(results):
                    chosen.append(results[n - 1]["name"])
        if not chosen:
            self.message("Package search", "No valid selection.")
            return
        combined = f"{self.config['extra_packages']} {' '.join(chosen)}"
        self.config["extra_packages"] = self.dedupe_packages(combined)
        self.status = "Added: " + ", ".join(chosen)

    def prompt_multiline(self, title: str, lines: list[str]) -> str | None:
        self.clear()
        self.draw_header(title)
        h, w = self.stdscr.getmaxyx()
        for i, line in enumerate(lines[: max(1, h - 8)], start=3):
            self.stdscr.addnstr(i, 2, self.truncate(line, w - 4), w - 4)
        self.stdscr.addnstr(h - 4, 2, "Selection: ", w - 4, self.color(1))
        self.draw_footer()
        self.stdscr.refresh()
        curses.curs_set(1)
        curses.echo()
        try:
            data = self.stdscr.getstr(h - 4, 13, 80).decode(errors="ignore").strip()
            return data or None
        finally:
            curses.noecho()
            curses.curs_set(0)

    def draw_wait(self, title: str, message: str):
        self.clear()
        self.draw_header(title)
        self.stdscr.addnstr(5, 2, message, self.stdscr.getmaxyx()[1] - 4, self.color(3))
        self.draw_footer()
        self.stdscr.refresh()

    def message(self, title: str, message: str, error: bool = False):
        self.clear()
        self.draw_header(title)
        h, w = self.stdscr.getmaxyx()
        attr = self.color(4 if error else 2, True)
        for i, line in enumerate(message.splitlines() or [message], start=4):
            if i >= h - 3:
                break
            self.stdscr.addnstr(i, 2, self.truncate(line, w - 4), w - 4, attr if i == 4 else curses.A_NORMAL)
        self.stdscr.addnstr(h - 3, 2, "Press any key to continue…", w - 4, self.color(1))
        self.draw_footer()
        self.stdscr.refresh()
        self.stdscr.getch()

    def confirm_curses(self, prompt: str) -> bool:
        self.clear()
        self.draw_header("Confirm")
        self.stdscr.addnstr(5, 2, prompt, self.stdscr.getmaxyx()[1] - 4, self.color(3, True))
        self.stdscr.addnstr(7, 2, "Press y to confirm, anything else to cancel.", self.stdscr.getmaxyx()[1] - 4)
        self.draw_footer()
        self.stdscr.refresh()
        return self.stdscr.getch() in (ord("y"), ord("Y"), ord("s"), ord("S"))

    def namespace(self, dry_run: bool = False, yes: bool = True) -> SimpleNamespace:
        return SimpleNamespace(
            output=self.config["output"],
            image_size=self.config["image_size"],
            branch=self.config["branch"],
            arch=self.config["arch"],
            hostname=self.config["hostname"],
            user=self.config["user"],
            password=self.config["password"],
            root_password=self.config["root_password"],
            ask_password=False,
            timezone=self.config["timezone"],
            locale=self.config["locale"],
            language=self.config["language"],
            console_keymap=self.config["console_keymap"],
            xkb_layout=self.config["xkb_layout"],
            xkb_variant=self.config["xkb_variant"],
            xkb_model=self.config["xkb_model"],
            desktop=self.config["desktop"],
            display_manager=self.config["display_manager"],
            default_session=self.config["default_session"],
            wm=list(self.config["wms"]),
            tiling_wms="",
            browser=self.config["browser"],
            audio=self.config["audio"],
            network=self.config["network"],
            wifi=self.config["wifi"],
            bluetooth=self.config["bluetooth"],
            bootloader=self.config["bootloader"],
            kernel=self.config["kernel"],
            firmware=self.config["firmware"],
            boot_timeout=int(self.config["boot_timeout"] or 3),
            systemd_boot_console_mode=self.config["systemd_boot_console_mode"],
            auto_resize=self.config["auto_resize"],
            extra_package=None,
            extra_packages=self.config["extra_packages"],
            dry_run=dry_run,
            yes=yes,
        )

    def suspend(self, func):
        curses.def_prog_mode()
        curses.endwin()
        try:
            return func()
        finally:
            input("\nPress Enter to return to TUI…")
            self.stdscr.refresh()
            curses.reset_prog_mode()
            curses.curs_set(0)
            self.stdscr.keypad(True)

    def build_screen(self):
        while True:
            env = cli.env_from_build_args(self.namespace(dry_run=True))
            items = [
                ("Output", self.config["output"]),
                ("Profile", f"{self.config['desktop']} / {self.config['display_manager']} / {self.config['bootloader']}"),
                ("Extra packages", self.config["extra_packages"] or "none"),
                ("Validate dry-run", "print generated package list"),
                ("Build image", "run full image build"),
                ("Back", "return"),
            ]
            choice = self.menu("Build image", items)
            if choice is None or choice == 5:
                return
            if choice == 0:
                value = self.prompt("Output image path", self.config["output"])
                if value:
                    self.config["output"] = value
            elif choice == 3:
                self.suspend(lambda: cli.cmd_build(self.namespace(dry_run=True, yes=True)))
            elif choice == 4:
                if self.confirm_curses("Build the image now? This can take a while."):
                    self.suspend(lambda: cli.cmd_build(self.namespace(dry_run=False, yes=True)))
            else:
                self.message("Build profile", "\n".join(f"{k}={v}" for k, v in env.items() if k.startswith("ALPINE_USB_") or k in {"IMAGE_SIZE", "ALPINE_BRANCH", "ARCH"}))

    def usb_screen(self):
        while True:
            device_text = self.config["device"] or "none"
            items = [
                ("Selected device", device_text),
                ("Refresh/list devices", "detect removable USB drives"),
                ("Enter device manually", "/dev/diskX or /dev/sdX"),
                ("Flash selected image", self.config["output"]),
                ("Back", "return"),
            ]
            choice = self.menu("USB target and flashing", items)
            if choice is None or choice == 4:
                return
            if choice == 1:
                self.device_list_screen()
            elif choice == 2:
                value = self.prompt("Manual USB device", self.config["device"] or ("/dev/diskX" if sys.platform == "darwin" else "/dev/sdX"))
                if value:
                    self.config["device"] = value
            elif choice == 3:
                if not self.config["device"]:
                    self.message("Flash USB", "Select or enter a device first.", error=True)
                    continue
                if self.confirm_curses("Flash selected image and ERASE the target USB?"):
                    ns = SimpleNamespace(image=self.config["output"], device=self.config["device"], yes=True)
                    self.suspend(lambda: cli.cmd_flash(ns))

    def device_list_screen(self):
        self.draw_wait("USB devices", "Scanning removable USB devices…")
        devices = cli.list_devices()
        self.last_devices = devices
        if not devices:
            self.message("USB devices", "No removable USB-like devices detected. You can still enter a device manually.")
            return
        items = [(dev, label) for dev, label in devices] + [("Back", "return")]
        choice = self.menu("Select USB device", items)
        if choice is not None and choice < len(devices):
            self.config["device"] = devices[choice][0]
            self.status = f"Selected USB target: {self.config['device']}"

    def doctor(self):
        self.suspend(lambda: cli.cmd_doctor(SimpleNamespace()))

    def main_menu(self):
        while True:
            items = [
                ("System, user, localization", f"{self.config['user']}@{self.config['hostname']}  {self.config['locale']}  {self.config['xkb_layout']}"),
                ("Desktop, sessions, WMs", f"{self.config['desktop']}  dm={self.config['display_manager']}  wms={','.join(self.config['wms']) or 'none'}"),
                ("Network, Wi-Fi, Bluetooth", f"{self.config['network']}  wifi={self.config['wifi']}  bluetooth={self.config['bluetooth']}"),
                ("Bootloader, kernel, firmware", f"{self.config['bootloader']}  linux-{self.config['kernel']}  firmware={self.config['firmware']}"),
                ("Extra APK packages", self.config["extra_packages"] or "search/add packages"),
                ("Build image", self.config["output"]),
                ("USB devices and flash", self.config["device"] or "select target USB"),
                ("Doctor", "check host tools"),
                ("Quit", "exit TUI"),
            ]
            choice = self.menu("Main menu", items)
            if choice is None or choice == 8:
                if self.confirm_curses("Quit Alpine USB Installer TUI?"):
                    raise TuiExit
            elif choice == 0:
                self.edit_fields("System, user, localization", [
                    ("Output image path", "output", "text"),
                    ("Minimum image size", "image_size", "choice"),
                    ("Alpine branch", "branch", "choice"),
                    ("Architecture", "arch", "choice"),
                    ("Hostname", "hostname", "text"),
                    ("User", "user", "text"),
                    ("User password", "password", "password"),
                    ("Root password", "root_password", "password"),
                    ("Timezone", "timezone", "choice"),
                    ("Locale", "locale", "choice"),
                    ("Language", "language", "text"),
                    ("Console keymap", "console_keymap", "choice"),
                    ("XKB layout", "xkb_layout", "choice"),
                    ("XKB variant", "xkb_variant", "text"),
                    ("XKB model", "xkb_model", "text"),
                ])
            elif choice == 1:
                self.edit_fields("Desktop, sessions, WMs", [
                    ("Desktop", "desktop", "choice"),
                    ("Display manager", "display_manager", "choice"),
                    ("Default session", "default_session", "choice"),
                    ("Optional WMs", "wms", "multi_wm"),
                    ("Browser", "browser", "choice"),
                    ("Audio", "audio", "choice"),
                ])
            elif choice == 2:
                self.edit_fields("Network, Wi-Fi, Bluetooth", [
                    ("Network backend", "network", "choice"),
                    ("Wi-Fi support", "wifi", "bool"),
                    ("Bluetooth support", "bluetooth", "bool"),
                ])
            elif choice == 3:
                self.edit_fields("Bootloader, kernel, firmware", [
                    ("Bootloader", "bootloader", "choice"),
                    ("Kernel", "kernel", "choice"),
                    ("Firmware", "firmware", "choice"),
                    ("Boot menu timeout", "boot_timeout", "text"),
                    ("systemd-boot console-mode", "systemd_boot_console_mode", "choice"),
                    ("Auto-resize USB", "auto_resize", "bool"),
                ])
            elif choice == 4:
                self.extra_packages_screen()
            elif choice == 5:
                self.build_screen()
            elif choice == 6:
                self.usb_screen()
            elif choice == 7:
                self.doctor()


def run_tui(stdscr):
    app = TuiApp(stdscr)
    try:
        app.main_menu()
    except TuiExit:
        return 0
    return 0


def self_test() -> int:
    app_config = dict(DEFAULT_CONFIG)
    app_config["wms"] = ["i3", "sway"]
    assert app_config["desktop"] == "xfce"
    assert "systemd-boot" in CHOICES["bootloader"]
    ns = SimpleNamespace(
        output=app_config["output"], image_size=app_config["image_size"], branch=app_config["branch"], arch=app_config["arch"],
        hostname=app_config["hostname"], user=app_config["user"], password=app_config["password"], root_password=app_config["root_password"],
        ask_password=False, timezone=app_config["timezone"], locale=app_config["locale"], language=app_config["language"],
        console_keymap=app_config["console_keymap"], xkb_layout=app_config["xkb_layout"], xkb_variant=app_config["xkb_variant"], xkb_model=app_config["xkb_model"],
        desktop=app_config["desktop"], display_manager=app_config["display_manager"], default_session=app_config["default_session"],
        wm=app_config["wms"], tiling_wms="", browser=app_config["browser"], audio=app_config["audio"], network=app_config["network"],
        wifi=app_config["wifi"], bluetooth=app_config["bluetooth"], bootloader=app_config["bootloader"], kernel=app_config["kernel"],
        firmware=app_config["firmware"], boot_timeout=int(app_config["boot_timeout"]), systemd_boot_console_mode=app_config["systemd_boot_console_mode"],
        auto_resize=app_config["auto_resize"], extra_package=None, extra_packages=app_config["extra_packages"], dry_run=True, yes=True,
    )
    env = cli.env_from_build_args(ns)
    assert env["ALPINE_USB_TILING_WMS"] == "i3 sway"
    print("TUI self-test passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Complete curses TUI for Alpine USB Installer")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("The TUI needs an interactive terminal. Use ./run_cli.sh for non-interactive mode.", file=sys.stderr)
        return 1
    return curses.wrapper(run_tui)


if __name__ == "__main__":
    raise SystemExit(main())
