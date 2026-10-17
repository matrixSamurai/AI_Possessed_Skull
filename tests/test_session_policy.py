from malachi.behavior.session_policy import SessionPolicy


def test_idle_boundary(settings):
    p = SessionPolicy(settings)
    p.start(0)
    assert p.end_reason(29.999) is None
    assert p.end_reason(30) == "inactivity"


def test_activity_and_speaking(settings):
    p = SessionPolicy(settings)
    p.start(0)
    p.event("user_start", 20)
    assert p.end_reason(60) is None
    p.event("user_end", 60)
    assert p.end_reason(89.99) is None
    assert p.end_reason(90) == "inactivity"
    p.event("agent_start", 90)
    assert p.end_reason(120) is None
    p.event("agent_end", 120)
    assert p.end_reason(150) == "inactivity"


def test_absence_recovers(settings):
    settings.visitor_absence_timeout_seconds = 10
    p = SessionPolicy(settings)
    p.start(0)
    p.update_presence(False, 1)
    assert p.end_reason(10.999) is None
    p.update_presence(True, 10)
    assert p.end_reason(11) is None
    p.update_presence(False, 11)
    assert p.end_reason(21) == "visitor absent"


def test_maximum_duration_even_while_speaking(settings):
    p = SessionPolicy(settings)
    p.start(0)
    p.event("agent_start", 1)
    assert p.end_reason(179.999) is None
    assert p.end_reason(180) == "maximum duration"


def test_three_unanswered_turns_wait_for_speech_to_finish(settings):
    p = SessionPolicy(settings)
    p.start(0)
    for now in (1, 3):
        p.event("agent_response", now)
        p.event("agent_start", now)
        p.event("agent_end", now + 1)
        assert p.end_reason(now + 2) is None
    p.event("agent_response", 5)
    assert p.end_reason(6) is None  # Response text is not completed playback.
    p.event("agent_start", 7)
    assert p.end_reason(8) is None
    p.event("agent_end", 9)
    assert p.end_reason(10.49) is None
    assert p.end_reason(10.5) == "no user response after agent turns"


def test_user_transcript_resets_limit_but_activity_does_not(settings):
    p = SessionPolicy(settings)
    p.start(0)
    for now in (1, 2, 3):
        p.event("agent_response", now)
    p.event("activity", 4)
    assert p.unanswered_turns == 3
    p.event("user_start", 4)
    p.event("user_end", 5)
    assert p.unanswered_turns == 3  # Noise alone is not a transcribed response.
    p.event("user_response", 6)
    assert p.unanswered_turns == 0
    p.event("agent_start", 7)
    p.event("agent_end", 8)
    assert p.end_reason(10) is None
    p.start(11)
    assert p.unanswered_turns == 0


def test_speech_pauses_do_not_count_as_separate_turns(settings):
    p = SessionPolicy(settings)
    p.start(0)
    p.event("agent_response", 1)
    for now in range(2, 10):
        p.event("agent_start", now)
        p.event("agent_end", now + 0.1)
    assert p.unanswered_turns == 1
    assert p.end_reason(12) is None
