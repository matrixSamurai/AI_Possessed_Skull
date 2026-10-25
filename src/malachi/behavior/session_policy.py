class SessionPolicy:
    """Bounded monotonic session timers; idle never cuts off active speech."""

    def __init__(self, settings):
        self.settings = settings
        self.started = self.activity = 0.0
        self.user_speaking = self.agent_speaking = False
        self.absent_since = None
        self.unanswered_turns = 0
        self.limit_audio_started = False
        self.unanswered_finished_at = None

    def start(self, now):
        self.started = self.activity = now
        self.user_speaking = self.agent_speaking = False
        self.absent_since = None
        self.unanswered_turns = 0
        self.limit_audio_started = False
        self.unanswered_finished_at = None

    def update_presence(self, present, now):
        if present:
            self.absent_since = None
        elif self.absent_since is None:
            self.absent_since = now

    def event(self, kind, now):
        if kind == "user_response":
            self.unanswered_turns = 0
            self.limit_audio_started = False
            self.unanswered_finished_at = None
            self.activity = now
        elif kind == "agent_response":
            # Count provider response turns, never PCM blocks or pauses in speech.
            self.unanswered_turns += 1
        elif kind == "agent_start":
            self.unanswered_finished_at = None
            if self.unanswered_turns >= self.settings.max_unanswered_agent_turns:
                self.limit_audio_started = True
        elif kind == "agent_end" and self.limit_audio_started:
            self.unanswered_finished_at = now
        if kind in ("activity", "user_start", "user_end", "agent_start", "agent_end"):
            self.activity = now
        if kind in ("user_start", "user_end"):
            self.user_speaking = kind == "user_start"
        if kind in ("agent_start", "agent_end"):
            self.agent_speaking = kind == "agent_start"

    def end_reason(self, now):
        if now - self.started >= self.settings.max_session_duration_seconds:
            return "maximum duration"
        if (
            self.absent_since is not None
            and now - self.absent_since >= self.settings.visitor_absence_timeout_seconds
        ):
            return "visitor absent"
        if (
            self.unanswered_turns >= self.settings.max_unanswered_agent_turns
            and self.unanswered_finished_at is not None
            and now - self.unanswered_finished_at >= 1.5
            and not self.agent_speaking
            and not self.user_speaking
        ):
            return "no user response after agent turns"
        if (
            not self.user_speaking
            and not self.agent_speaking
            and now - self.activity >= self.settings.conversation_idle_timeout_seconds
        ):
            return "inactivity"
        return None
