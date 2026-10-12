import math
import random
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QRadialGradient, QFont, QPainterPath, QPen
from PySide6.QtWidgets import QWidget
from malachi.ui.eye_effects import EyeEffects


class AnimatedSkull(QWidget):
    def __init__(self, motion, eyes):
        super().__init__()
        self.motion, self.eyes = motion, eyes
        self.blink = False
        self.effects = EyeEffects()
        self.veins = self._vein_paths()
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
            self._paint_eye(p, x)
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

    @staticmethod
    def _vein_paths():
        rng = random.Random(73)
        paths = []
        for i in range(12):
            angle = i * math.tau / 12 + rng.uniform(-0.1, 0.1)
            radius = rng.uniform(19, 26)
            outer = QPointF(math.cos(angle) * 43, math.sin(angle) * 38)
            inner = QPointF(math.cos(angle) * radius, math.sin(angle) * radius * 0.8)
            bend = QPointF(
                (outer.x() + inner.x()) / 2 + rng.uniform(-5, 5),
                (outer.y() + inner.y()) / 2 + rng.uniform(-5, 5),
            )
            path = QPainterPath(outer)
            path.quadTo(bend, inner)
            branch = QPainterPath(bend)
            branch.lineTo(QPointF(bend.x() + rng.uniform(-9, 9), bend.y() + rng.uniform(-8, 8)))
            paths.append((path, branch))
        return paths

    @staticmethod
    def _blend(a, b, amount):
        a, b = QColor(a), QColor(b)
        return QColor(
            round(a.red() + (b.red() - a.red()) * amount),
            round(a.green() + (b.green() - a.green()) * amount),
            round(a.blue() + (b.blue() - a.blue()) * amount),
        )

    def _paint_eye(self, p, x):
        fury, phase = self.effects.intensity, self.effects.phase
        rect = QRectF(x - 42, -85, 84, 74)
        breathing = 0.92 + 0.08 * math.sin(phase * 1.5)
        halo = QRadialGradient(x, -48, 68)
        halo.setColorAt(0, QColor(210, 15, 42, round(100 * fury * breathing)))
        halo.setColorAt(1, QColor(160, 0, 30, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QRectF(x - 68, -116, 136, 136))
        p.save()
        clip = QPainterPath()
        clip.addEllipse(rect)
        p.setClipPath(clip)
        sclera = QRadialGradient(x - 9, -62, 62)
        sclera.setColorAt(0, self._blend("#faf3df", "#f4b3a8", fury * 0.65))
        sclera.setColorAt(1, self._blend("#a9aaa6", "#a84451", fury * 0.7))
        p.setBrush(sclera)
        p.drawEllipse(rect)
        p.save()
        p.translate(x, -48)
        for i, (path, branch) in enumerate(self.veins):
            reveal = max(0, min(1, (fury - i * 0.025) * 1.5))
            p.setPen(QPen(QColor(140, 12, 38, round(190 * reveal)), 0.7 + fury * 0.7))
            p.drawPath(path)
            p.setPen(QPen(QColor(170, 20, 42, round(130 * reveal)), 0.65))
            p.drawPath(branch)
        p.restore()
        px, py = x + self.motion.x * 23, -48 + self.motion.y * 18
        iris = QRadialGradient(px - 4, py - 5, 26)
        iris.setColorAt(0, self._blend("#9cf0d2", "#ff8157", fury))
        iris.setColorAt(0.55, self._blend("#277a80", "#c01636", fury))
        iris.setColorAt(1, self._blend("#102e42", "#390514", fury))
        p.setPen(QPen(QColor("#17121e"), 1.5))
        p.setBrush(iris)
        p.drawEllipse(QRectF(px - 23, py - 23, 46, 46))
        p.setPen(QPen(QColor(255, 185, 120, round(25 + 60 * fury)), 0.6))
        for i in range(32):
            angle = i * math.tau / 32 + phase * 0.025
            p.drawLine(
                QPointF(px + math.cos(angle) * 12, py + math.sin(angle) * 12),
                QPointF(px + math.cos(angle) * 21, py + math.sin(angle) * 21),
            )
        pupil = 8.5 - 4 * fury + math.sin(phase * 1.2) * 0.4
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#07060b"))
        p.drawEllipse(QRectF(px - pupil, py - 14, pupil * 2, 28))
        p.setBrush(QColor(255, 246, 221, 225))
        p.drawEllipse(QRectF(px - 8, py - 13, 5, 5))
        p.setBrush(QColor(255, 246, 221, 85))
        p.drawEllipse(QRectF(px + 9, py + 8, 3, 3))
        # Inward-slanting lids build a theatrical angry stare.
        lid = QPainterPath(QPointF(x - 46, -89))
        lid.lineTo(x + 46, -89)
        if x < 0:
            lid.lineTo(x + 46, -84 + 27 * fury)
            lid.lineTo(x - 46, -84 + 6 * fury)
        else:
            lid.lineTo(x + 46, -84 + 6 * fury)
            lid.lineTo(x - 46, -84 + 27 * fury)
        lid.closeSubpath()
        p.setBrush(QColor("#9c9691"))
        p.drawPath(lid)
        if self.blink:
            p.drawEllipse(rect)
        p.restore()
        p.setPen(Qt.PenStyle.NoPen)
