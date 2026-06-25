from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


def make_app_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor("#111827"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(QColor("#93c5fd"))
    painter.drawRoundedRect(10, 8, 44, 48, 8, 8)
    painter.setBrush(QColor("#16a34a"))
    painter.setPen(QColor("#bbf7d0"))
    painter.drawRoundedRect(22, 4, 20, 12, 4, 4)
    painter.setPen(QColor("#ffffff"))
    painter.drawLine(24, 34, 32, 24)
    painter.drawLine(32, 24, 40, 34)
    painter.drawLine(32, 24, 32, 44)
    painter.end()
    return QIcon(pix)


def make_button_icon(kind: str, size: int = 20) -> QIcon:
    dpr = 2
    pixel_size = max(size, int(size * dpr))
    pix = QPixmap(pixel_size, pixel_size)
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 20
    pen = QPen(QColor("#ffffff"), max(1.0, 1.15 * scale))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    def pts(items):
        return [QPoint(x, y) for x, y in items]

    def xy(v):
        return int(v * scale)

    if kind == "config":
        p.drawEllipse(xy(6), xy(6), xy(8), xy(8))
        p.drawEllipse(xy(8), xy(8), xy(4), xy(4))
        for x1, y1, x2, y2 in [
            (10, 2, 10, 5),
            (10, 15, 10, 18),
            (2, 10, 5, 10),
            (15, 10, 18, 10),
            (4, 4, 6, 6),
            (14, 14, 16, 16),
            (16, 4, 14, 6),
            (6, 14, 4, 16),
        ]:
            p.drawLine(xy(x1), xy(y1), xy(x2), xy(y2))
    elif kind == "desktop":
        p.drawRect(xy(3), xy(4), xy(14), xy(9))
        p.drawLine(xy(8), xy(16), xy(12), xy(16))
        p.drawLine(xy(10), xy(13), xy(10), xy(16))
    elif kind == "network":
        p.drawEllipse(xy(3), xy(3), xy(14), xy(14))
        p.drawLine(xy(3), xy(10), xy(17), xy(10))
        p.drawArc(xy(6), xy(3), xy(8), xy(14), 90 * 16, 180 * 16)
        p.drawArc(xy(6), xy(3), xy(8), xy(14), 270 * 16, 180 * 16)
    elif kind == "disk":
        p.drawEllipse(xy(4), xy(3), xy(12), xy(4))
        p.drawLine(xy(4), xy(5), xy(4), xy(15))
        p.drawLine(xy(16), xy(5), xy(16), xy(15))
        p.drawEllipse(xy(4), xy(13), xy(12), xy(4))
        p.drawArc(xy(4), xy(8), xy(12), xy(4), 180 * 16, 180 * 16)
    elif kind == "package":
        p.drawPolyline(
            pts(
                [
                    (xy(10), xy(2)),
                    (xy(17), xy(6)),
                    (xy(17), xy(14)),
                    (xy(10), xy(18)),
                    (xy(3), xy(14)),
                    (xy(3), xy(6)),
                    (xy(10), xy(2)),
                ]
            )
        )
        p.drawLine(xy(3), xy(6), xy(10), xy(10))
        p.drawLine(xy(17), xy(6), xy(10), xy(10))
        p.drawLine(xy(10), xy(10), xy(10), xy(18))
    elif kind == "console":
        p.drawRect(xy(3), xy(4), xy(14), xy(12))
        p.drawLine(xy(6), xy(8), xy(9), xy(10))
        p.drawLine(xy(6), xy(12), xy(12), xy(12))
    elif kind in {"eye", "eye_off"}:
        p.drawEllipse(xy(3), xy(6), xy(14), xy(8))
        p.drawEllipse(xy(8), xy(8), xy(4), xy(4))
        if kind == "eye_off":
            p.drawLine(xy(4), xy(17), xy(16), xy(3))
    elif kind == "folder":
        p.drawPolyline(
            pts(
                [
                    (xy(3), xy(7)),
                    (xy(3), xy(16)),
                    (xy(17), xy(16)),
                    (xy(17), xy(6)),
                    (xy(9), xy(6)),
                    (xy(7), xy(4)),
                    (xy(3), xy(4)),
                    (xy(3), xy(7)),
                ]
            )
        )
    elif kind == "build":
        p.drawLine(xy(10), xy(3), xy(10), xy(14))
        p.drawLine(xy(6), xy(7), xy(10), xy(3))
        p.drawLine(xy(14), xy(7), xy(10), xy(3))
        p.drawLine(xy(4), xy(16), xy(16), xy(16))
    elif kind == "usb":
        p.drawLine(xy(10), xy(3), xy(10), xy(14))
        p.drawLine(xy(6), xy(7), xy(14), xy(7))
        p.drawEllipse(xy(5), xy(6), xy(2), xy(2))
        p.drawRect(xy(13), xy(5), xy(3), xy(3))
        p.drawEllipse(xy(8), xy(14), xy(4), xy(4))
    elif kind == "flash":
        p.drawPolyline(
            pts(
                [
                    (xy(11), xy(2)),
                    (xy(5), xy(11)),
                    (xy(10), xy(11)),
                    (xy(8), xy(18)),
                    (xy(15), xy(8)),
                    (xy(10), xy(8)),
                    (xy(11), xy(2)),
                ]
            )
        )
    elif kind == "refresh":
        p.drawArc(xy(5), xy(5), xy(10), xy(10), 35 * 16, 285 * 16)
        p.drawLine(xy(14), xy(5), xy(14), xy(9))
        p.drawLine(xy(14), xy(5), xy(10), xy(5))
    elif kind == "check":
        p.drawLine(xy(4), xy(10), xy(8), xy(15))
        p.drawLine(xy(8), xy(15), xy(16), xy(5))
    elif kind == "warn":
        p.drawPolyline(pts([(xy(10), xy(3)), (xy(18), xy(17)), (xy(2), xy(17)), (xy(10), xy(3))]))
        p.drawLine(xy(10), xy(7), xy(10), xy(12))
        p.drawPoint(xy(10), xy(15))
    elif kind == "error":
        p.drawEllipse(xy(3), xy(3), xy(14), xy(14))
        p.drawLine(xy(7), xy(7), xy(13), xy(13))
        p.drawLine(xy(13), xy(7), xy(7), xy(13))
    p.end()
    return QIcon(pix)


def icon_label(kind: str, size: int = 18) -> QLabel:
    label = QLabel()
    label.setPixmap(make_button_icon(kind, size).pixmap(size, size))
    label.setFixedSize(size + 2, size + 2)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def title_widget(label: QLabel, icon_kind: str) -> QWidget:
    widget = QWidget()
    widget.setStyleSheet("background:transparent;border:0;")
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(icon_label(icon_kind, 18))
    layout.addWidget(label)
    layout.addStretch(1)
    return widget
