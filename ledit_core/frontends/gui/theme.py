from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

BREEZE_WINDOW = "#232629"
BREEZE_VIEW = "#1b1e20"
BREEZE_PANEL = "#31363b"
BREEZE_PANEL_ALT = "#2a2e32"
BREEZE_BORDER = "#4b5057"
BREEZE_TEXT = "#eff0f1"
BREEZE_SUBTLE = "#bdc3c7"
BREEZE_BLUE = "#1f5f85"
BREEZE_BLUE_HOVER = "#26729f"
BREEZE_RED = "#8f2731"
BREEZE_RED_HOVER = "#a8323d"
BREEZE_DANGER_TEXT = "#ff6b7a"
BREEZE_GREEN = "#1f6f43"
BREEZE_GREEN_HOVER = "#268452"
BREEZE_YELLOW = "#fdbc4b"
BREEZE_ORANGE = "#8a5a12"
BREEZE_ORANGE_HOVER = "#a66d17"
BREEZE_PURPLE = "#5b2d72"
BREEZE_PURPLE_HOVER = "#6d3688"
BREEZE_DISABLED = "#4d5358"
BREEZE_DISABLED_TEXT = "#9aa0a6"


def button_style(bg: str = BREEZE_BLUE, hover: str = BREEZE_BLUE_HOVER) -> str:
    return (
        "QPushButton { "
        f"background:{bg};color:{BREEZE_TEXT};border:1px solid {BREEZE_BORDER};"
        "border-radius:4px;padding:3px 8px;min-height:24px;"
        " }"
        f" QPushButton:hover {{ background:{hover}; }}"
        f" QPushButton:disabled {{ background:{BREEZE_DISABLED};color:{BREEZE_DISABLED_TEXT}; }}"
    )


def apply_breeze_theme(app: QApplication):
    available_styles = QStyleFactory.keys()
    style = "Breeze" if "Breeze" in available_styles else "Fusion"
    app.setStyle(style)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BREEZE_WINDOW))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(BREEZE_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(BREEZE_VIEW))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BREEZE_PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BREEZE_PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(BREEZE_TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(BREEZE_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(BREEZE_PANEL))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(BREEZE_TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(BREEZE_DANGER_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(BREEZE_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
