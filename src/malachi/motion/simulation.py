from malachi.motion.controller import clamp


class SimulatedMotionController:
    def __init__(self):
        self.x = self.y = self.jaw = self.head_x = self.head_y = 0.0
        self.led = "off"
        self.stopped = False

    def set_eye_target(self, x, y):
        if not self.stopped:
            self.x, self.y = clamp(x), clamp(y)

    def set_jaw_position(self, value):
        if not self.stopped:
            self.jaw = clamp(value, 0, 1)

    def set_head_target(self, x, y):
        if not self.stopped:
            self.head_x, self.head_y = clamp(x), clamp(y)

    def set_led_effect(self, effect):
        if not self.stopped:
            self.led = effect

    def neutral_position(self):
        self.x, self.y, self.jaw = 0.0, 0.3, 0.0
        self.head_x = self.head_y = 0.0

    def emergency_stop(self):
        self.neutral_position()
        self.stopped = True
