class SessionPolicy:
    """Bounded monotonic session timers; idle never cuts off active speech."""

    def __init__(self, settings):
        self.settings = settings
        self.started = self.activity = 0.0
        self.user_speaking = self.agent_speaking = False
        self.absent_since = None

    def start(self, now):
        self.started = self.activity = now
        self.user_speaking = self.agent_speaking = False
        self.absent_since = None

    def update_presence(self, present, now):
        if present:
            self.absent_since = None
        elif self.absent_since is None:
            self.absent_since = now

    def event(self, kind, now):
        if kind in ("activity", "user_start", "user_end", "agent_start", "agent_end"):
            self.activity = now
        if kind.startswith("user_"):
            self.user_speaking = kind == "user_start"
        if kind.startswith("agent_"):
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
            not self.user_speaking
            and not self.agent_speaking
            and now - self.activity >= self.settings.conversation_idle_timeout_seconds
        ):
            return "inactivity"
        return None
