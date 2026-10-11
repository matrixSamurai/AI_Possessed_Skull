"""Frame-change motion heuristic, not semantic object detection."""

import cv2
import numpy as np


class MotionDetector:
    def __init__(self, settings):
        self.settings = settings
        self.previous = None
        self.score = 0.0

    def reset(self):
        self.previous = None
        self.score = 0.0

    def update(self, frame):
        gray = cv2.cvtColor(cv2.resize(frame, (160, 120)), cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self.previous is None:
            self.previous = gray
            return False
        mask = cv2.absdiff(gray, self.previous) >= self.settings.motion_pixel_threshold
        self.previous = gray
        self.score = float(np.mean(mask))
        # Global changes are commonly exposure shifts/camera relocation, not an object.
        return self.settings.motion_area_threshold <= self.score <= 0.6
