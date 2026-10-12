import math
import random
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QRadialGradient, QFont, QPainterPath, QPen, QImage
from PySide6.QtWidgets import QWidget
from malachi.ui.eye_effects import EyeEffects


class AnimatedSkull(QWidget):
    def __init__(self, motion, eyes):
        super().__init__()
        self.motion, self.eyes = motion, eyes
        self.blink = False
        self.effects = EyeEffects()
        self.reflection = None
        self.reflection_updated = float("-inf")
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
            f"{self.effects.preset.upper()} GAZE   •   PAN {self.eyes.angles()[0]:+.1f}°   TILT {self.eyes.angles()[1]:+.1f}°",
        )
        p.end()

    def set_reflection(self, frame, now, face=None):
        if frame is None:
            self.reflection = None
            return
        if now - self.reflection_updated < 0.2:
            return
        import cv2

        if face is not None:
            height, width = frame.shape[:2]
            x1, y1, x2, y2 = face.box
            dx, dy = (x2 - x1) * 0.4, (y2 - y1) * 0.4
            left, right = max(0, int((x1 - dx) * width)), min(width, int((x2 + dx) * width))
            top, bottom = max(0, int((y1 - dy) * height)), min(height, int((y2 + dy) * height))
            if right > left and bottom > top:
                frame = frame[top:bottom, left:right]
        rgb = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2RGB)
        self.reflection = (
            QImage(rgb.data, 160, 90, rgb.strides[0], QImage.Format.Format_RGB888)
            .copy()
            .mirrored(True, False)
        )
        self.reflection_updated = now

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
        energy, phase = self.effects.intensity, self.effects.phase
        fury = energy if self.effects.preset == "inferno" else energy * 0.25
        accent = QColor(*(round(c) for c in self.effects.accent))
        rect = QRectF(x - 42, -85, 84, 74)
        breathing = 0.92 + 0.08 * math.sin(phase * 1.5)
        halo = QRadialGradient(x, -48, 68)
        halo.setColorAt(
            0, QColor(accent.red(), accent.green(), accent.blue(), round(130 * energy * breathing))
        )
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
        iris.setColorAt(0, self._blend("#e0ffe9", accent.name(), energy))
        iris.setColorAt(0.55, self._blend("#277a80", accent.darker(135).name(), energy))
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
        self._paint_preset(p, px, py, accent, phase, energy)
        pupil = 8.5 - 4 * fury + math.sin(phase * 1.2) * 0.4
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#07060b"))
        if self.effects.preset == "mischievous":
            star = QPainterPath()
            for i in range(10):
                angle = i * math.pi / 5 - math.pi / 2 + phase * 0.15
                radius = 13 if i % 2 == 0 else 5
                point = QPointF(px + math.cos(angle) * radius, py + math.sin(angle) * radius)
                star.moveTo(point) if i == 0 else star.lineTo(point)
            star.closeSubpath()
            p.drawPath(star)
        elif self.effects.preset != "mirror":
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

    def _paint_preset(self, p, px, py, accent, phase, fury):
        p.save()
        preset = self.effects.preset
        if preset == "mirror" and self.reflection is not None:
            iris_clip = QPainterPath()
            iris_clip.addEllipse(QRectF(px - 22, py - 22, 44, 44))
            p.setClipPath(iris_clip, Qt.ClipOperation.IntersectClip)
            p.setOpacity(0.8)
            p.drawImage(QRectF(px - 37, py - 22, 74, 44), self.reflection)
        elif preset == "inferno":
            for i in range(9):
                x = px - 23 + i * 5.5
                height = 10 + fury * (14 + 9 * math.sin(phase * 2.4 + i * 1.7))
                flame = QPainterPath(QPointF(x - 4, py + 16))
                flame.cubicTo(
                    x - 9, py - 2, x + 6 * math.sin(phase + i), py - height, x, py - height - 6
                )
                flame.cubicTo(x + 9, py - height / 2, x + 7, py + 7, x + 4, py + 16)
                flame.closeSubpath()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 65 + i * 12, 10, round(100 * fury)))
                p.drawPath(flame)
        elif preset in ("spectral", "hypnosis"):
            for j in range(3):
                path = QPainterPath()
                for i in range(100):
                    angle = (
                        i * 0.12
                        + phase * (0.3 if preset == "hypnosis" else -0.2)
                        + j * math.tau / 3
                    )
                    radius = 2 + i * 0.2
                    point = QPointF(px + math.cos(angle) * radius, py + math.sin(angle) * radius)
                    path.moveTo(point) if i == 0 else path.lineTo(point)
                p.setPen(
                    QPen(
                        QColor(accent.red(), accent.green(), accent.blue(), 130),
                        1.2 if preset == "hypnosis" else 2.2,
                    )
                )
                p.drawPath(path)
        elif preset == "storm":
            for j in range(3):
                path = QPainterPath(QPointF(px - 23, py - 14 + j * 13))
                for i in range(1, 9):
                    path.lineTo(
                        px - 23 + i * 6, py - 14 + j * 13 + math.sin(i * 3 + phase * 1.5 + j) * 6
                    )
                p.setPen(QPen(QColor(225, 215, 255, 150), 1.3))
                p.drawPath(path)
        p.restore()
