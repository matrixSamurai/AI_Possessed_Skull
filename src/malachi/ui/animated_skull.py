from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QRadialGradient, QFont
from PySide6.QtWidgets import QWidget


class AnimatedSkull(QWidget):
    def __init__(self, motion, eyes):
        super().__init__()
        self.motion, self.eyes = motion, eyes
        self.blink = False
        self.setMinimumSize(360, 390)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2 - 5)
        scale = min(self.width() / 420, self.height() / 420)
        p.scale(scale, scale)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(0, -20, 220)
        glow.setColorAt(0, QColor("#34102a"))
        glow.setColorAt(1, QColor("#101017"))
        p.setBrush(glow)
        p.drawEllipse(QRectF(-210, -210, 420, 420))
        p.setBrush(QColor("#b0aaa4"))
        p.drawRoundedRect(QRectF(-145, -170, 290, 255), 110, 100)
        p.setBrush(QColor("#24202b"))
        p.drawEllipse(QRectF(-126, -98, 112, 102))
        p.drawEllipse(QRectF(14, -98, 112, 102))
        for x in (-70, 70):
            p.setBrush(QColor("#e5dfd6"))
            p.drawEllipse(QRectF(x - 42, -85, 84, 74))
            px, py = x + self.motion.x * 23, -48 + self.motion.y * 18
            iris = QRadialGradient(px, py, 24)
            iris.setColorAt(0, QColor("#ef6555"))
            iris.setColorAt(0.55, QColor("#9f192b"))
            iris.setColorAt(1, QColor("#2b0715"))
            p.setBrush(iris)
            p.drawEllipse(QRectF(px - 22, py - 22, 44, 44))
            p.setBrush(QColor("#07060b"))
            p.drawEllipse(QRectF(px - 8, py - 13, 16, 26))
            p.setBrush(QColor("#fff1da"))
            p.drawEllipse(QRectF(px - 7, py - 12, 5, 5))
            if self.blink:
                p.setBrush(QColor("#9c9691"))
                p.drawRoundedRect(QRectF(x - 43, -87, 86, 78), 25, 25)
        p.setBrush(QColor("#26202a"))
        p.drawEllipse(QRectF(-18, 0, 36, 39))
        opening = self.motion.jaw * 58
        p.drawRoundedRect(QRectF(-78, 62, 156, 20 + opening), 10, 10)
        p.setBrush(QColor("#cbc1b6"))
        for i in range(8):
            p.drawRoundedRect(QRectF(-76 + i * 19, 60, 16, 18), 3, 3)
            p.drawRoundedRect(QRectF(-76 + i * 19, 83 + opening, 16, 18), 3, 3)
        p.setBrush(QColor("#8e8581"))
        p.drawRoundedRect(QRectF(-86, 102 + opening, 172, 22), 12, 12)
        p.setPen(QColor("#bb819d"))
        p.setFont(QFont("Arial", 9))
        p.drawText(
            QRectF(-190, 180, 380, 25),
            Qt.AlignmentFlag.AlignCenter,
            f"SHARED EYES   •   PAN {self.eyes.angles()[0]:+.1f}°   TILT {self.eyes.angles()[1]:+.1f}°",
        )
        p.end()
