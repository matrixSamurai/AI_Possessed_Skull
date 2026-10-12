from enum import Enum
from malachi.behavior.session_policy import SessionPolicy


class State(str, Enum):
    IDLE = "IDLE"
    WATCHING = "WATCHING"
    STALKING = "STALKING"
    AWAKENING = "AWAKENING"
    CONVERSING = "CONVERSING"
    ENDING = "ENDING"
    COOLDOWN = "COOLDOWN"


class StateMachine:
    """Single owner of transitions. Caller serializes events on its control thread."""

    def __init__(self, settings, now=0.0):
        self.settings = settings
        self.state = self.previous = State.IDLE
        self.reason = "startup"
        self.entered = now
        self.detected_since = self.facing_since = self.last_seen = None
        self.absent_since = None
        self.autonomous = True
        self.emergency = False
        self.target_id = None
        self.session_target_id = None
        self.policy = SessionPolicy(settings)

    def transition(self, state, reason, now):
        if state == self.state:
            return
        self.previous, self.state = self.state, state
        self.reason, self.entered = reason, now

    def qualification(self, now):
        if self.facing_since is None:
            return 0.0
        return min(1.0, (now - self.facing_since) / self.settings.face_facing_hold_seconds)

    def tick(self, face, now):
        present = face is not None
        if present:
            self.last_seen = now
            self.absent_since = None
            if self.detected_since is None:
                self.detected_since = now
        elif self.absent_since is None:
            self.absent_since = now
        dropout = (
            not present
            and self.last_seen is not None
            and now - self.last_seen <= self.settings.face_dropout_seconds
        )
        if self.state == State.COOLDOWN:
            if (
                self.absent_since is not None
                and now - self.absent_since >= self.settings.cooldown_rearm_absence_seconds
            ):
                self.reset(now)
            return
        if self.state in (State.AWAKENING, State.CONVERSING):
            # Track IDs are geometric, not visitor identities: rapid motion/occlusion
            # can assign a new ID to the same person. Active sessions follow occupancy.
            if face is not None:
                self.session_target_id = face.track_id
            self.policy.update_presence(present, now)
            reason = self.policy.end_reason(now)
            if self.state == State.AWAKENING and now - self.entered >= 20:
                reason = "connection timeout"
            if reason:
                self.end(reason, now)
            return
        if self.state == State.ENDING or self.emergency:
            return
        if not present and not dropout:
            self.detected_since = self.facing_since = None
            self.transition(State.IDLE, "no visitor", now)
            return
        if not present:
            return
        if face.track_id != self.target_id:
            self.target_id = face.track_id
            self.detected_since = now
            self.facing_since = None
            self.transition(State.IDLE, "new geometric target", now)
        if now - self.detected_since < self.settings.face_detection_hold_seconds:
            return
        if self.state == State.IDLE:
            self.transition(State.WATCHING, "detection hold complete", now)
        facing = (
            abs(face.yaw - self.settings.neutral_yaw) <= self.settings.face_yaw_threshold
            and abs(face.pitch - self.settings.neutral_pitch) <= self.settings.face_pitch_threshold
        )
        if not facing or not self.autonomous or self.settings.conversation_backend == "disabled":
            self.facing_since = None
            self.transition(State.WATCHING, "tracking visitor", now)
        elif self.facing_since is None:
            self.facing_since = now
            self.transition(State.STALKING, "visitor facing skull", now)
        elif now >= self.facing_since + self.settings.face_facing_hold_seconds:
            self.start(now)

    def start(self, now):
        if self.emergency or self.state in (State.AWAKENING, State.CONVERSING, State.ENDING):
            return
        if self.settings.conversation_backend == "disabled":
            return
        self.session_target_id = self.target_id
        self.policy.start(now)
        self.transition(State.AWAKENING, "conversation requested", now)

    def event(self, event, now):
        if event.kind == "connected" and self.state == State.AWAKENING:
            self.policy.start(now)
            self.transition(State.CONVERSING, "session connected", now)
        elif event.kind in ("error", "goodbye"):
            self.end(event.kind, now)
        elif event.kind == "closed" and self.state in (
            State.AWAKENING,
            State.CONVERSING,
            State.ENDING,
        ):
            self.facing_since = None
            self.transition(State.COOLDOWN, "session closed", now)
        elif self.state == State.CONVERSING:
            self.policy.event(event.kind, now)

    def end(self, reason, now):
        if self.state in (State.AWAKENING, State.CONVERSING):
            self.transition(State.ENDING, reason, now)

    def reset(self, now):
        if self.state in (State.AWAKENING, State.CONVERSING, State.ENDING):
            return
        self.detected_since = self.facing_since = self.last_seen = self.absent_since = None
        self.target_id = self.session_target_id = None
        self.transition(State.IDLE, "rearmed", now)

    def stop(self, now):
        self.emergency = True
        self.autonomous = False
        self.end("emergency stop", now)
