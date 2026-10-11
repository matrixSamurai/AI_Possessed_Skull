import math


class FaceTracker:
    """Short-lived geometric tracks, never biometric identities."""

    def __init__(self):
        self.tracks = {}
        self.next_id = 1
        self.selected = None
        self.manual = None

    def select(self, faces, now):
        self.tracks = {k: v for k, v in self.tracks.items() if now - v[1] <= 0.5}
        remaining = set(self.tracks)
        current = []
        for face in sorted(faces, key=lambda f: self.area(f), reverse=True):
            choices = [
                (
                    math.hypot(
                        face.center_x - self.tracks[k][0].center_x,
                        face.center_y - self.tracks[k][0].center_y,
                    ),
                    k,
                )
                for k in remaining
            ]
            distance, key = min(choices) if choices else (1, None)
            if distance > 0.18:
                key = self.next_id
                self.next_id += 1
                face = face.model_copy(update={"track_id": key})
            else:
                remaining.remove(key)
                face = face.model_copy(update={"track_id": key, "stable": True})
            self.tracks[key] = face, now
            current.append(face)
        if not current:
            return None, current
        preferred = self.manual if self.manual is not None else self.selected
        chosen = next((f for f in current if f.track_id == preferred), None)
        chosen = chosen or max(current, key=self.area)
        self.selected = chosen.track_id
        return chosen, current

    @staticmethod
    def area(face):
        x1, y1, x2, y2 = face.box
        return (x2 - x1) * (y2 - y1)
