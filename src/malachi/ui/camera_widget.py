import cv2
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel


class CameraWidget(QLabel):
    selected = Signal(float, float)

    def __init__(self):
        super().__init__("Camera is stopped")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background:#09090e;border-radius:10px;color:#a398b4")
        self.image_size = None
        self.display_rect = None

    def show_frame(self, frame, faces, selected):
        if frame is None:
            return
        image = frame.copy()
        h, w = image.shape[:2]
        for face in faces:
            x1, y1, x2, y2 = face.box
            color = (
                (110, 80, 245)
                if selected and face.track_id == selected.track_id
                else (160, 140, 110)
            )
            cv2.rectangle(image, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), color, 2)
            cv2.putText(
                image,
                f"#{face.track_id} yaw {face.yaw:+.0f} pitch {face.pitch:+.0f}",
                (int(x1 * w), max(15, int(y1 * h) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
            )
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        qimage = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimage).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)
        self.display_rect = (
            (self.width() - pixmap.width()) / 2,
            (self.height() - pixmap.height()) / 2,
            pixmap.width(),
            pixmap.height(),
        )

    def mousePressEvent(self, event):
        if self.display_rect:
            x, y, w, h = self.display_rect
            point = event.position()
            if x <= point.x() <= x + w and y <= point.y() <= y + h:
                self.selected.emit((point.x() - x) / w, (point.y() - y) / h)
