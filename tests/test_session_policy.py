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
