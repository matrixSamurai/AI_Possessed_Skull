from malachi.behavior.state_machine import State, StateMachine
from malachi.events import ConversationEvent


def awaken(machine, face):
    machine.tick(face, 0)
    machine.tick(face, 0.3)
    machine.tick(face, 0.3 + machine.settings.face_facing_hold_seconds)


def test_detection_and_facing_hold(settings, face):
    m = StateMachine(settings)
    m.tick(face, 0)
    m.tick(face, 0.299)
    assert m.state == State.IDLE
    m.tick(face, 0.3)
    assert m.state == State.STALKING
    m.tick(face, 2.299)
    assert m.state == State.STALKING
    m.tick(face, 2.3)
    assert m.state == State.AWAKENING
    m.event(ConversationEvent(kind="connected"), 3.4)
    assert m.state == State.CONVERSING


def test_looking_away_resets_timer(settings, face):
    m = StateMachine(settings)
    m.tick(face, 0)
    m.tick(face, 0.3)
    m.tick(face.model_copy(update={"yaw": 40}), 2)
    assert m.state == State.WATCHING
    m.tick(face, 2.1)
    m.tick(face, 4)
    assert m.state == State.STALKING
    m.tick(face, 5.2)
    assert m.state == State.AWAKENING


def test_dropout_tolerance(settings, face):
    m = StateMachine(settings)
    m.tick(face, 0)
    m.tick(face, 0.3)
    m.tick(face, 1)
    m.tick(None, 1.2)
    assert m.state == State.STALKING
    m.tick(None, 1.251)
    assert m.state == State.IDLE
    assert m.facing_since is None


def test_cooldown_requires_absence(settings, face):
    m = StateMachine(settings)
    awaken(m, face)
    m.event(ConversationEvent(kind="connected"), 3.4)
    m.end("manual", 4)
    assert m.state == State.ENDING
    m.event(ConversationEvent(kind="closed"), 4.1)
    for t in (5, 10, 20):
        m.tick(face, t)
        assert m.state == State.COOLDOWN
    m.tick(None, 21)
    m.tick(None, 25.999)
    assert m.state == State.COOLDOWN
    m.tick(None, 26)
    assert m.state == State.IDLE


def test_emergency_latched(settings, face):
    m = StateMachine(settings)
    m.stop(0)
    m.start(2)
    m.tick(face, 3)
    assert m.state == State.IDLE
    assert m.emergency


def test_manual_start_duplicate_and_camera_absence(settings, face):
    settings.visitor_absence_timeout_seconds = 10
    m = StateMachine(settings)
    m.start(0)
    m.start(1)
    assert m.entered == 0
    m.event(ConversationEvent(kind="connected"), 1)
    m.tick(None, 2)
    m.tick(None, 11.999)
    assert m.state == State.CONVERSING
    m.tick(None, 12)
    assert m.state == State.ENDING
    assert m.reason == "visitor absent"


def test_disabled_conversations(settings, face):
    settings.conversation_backend = "disabled"
    m = StateMachine(settings)
    awaken(m, face)
    m.start(10)
    assert m.state == State.WATCHING


def test_connection_timeout(settings):
    m = StateMachine(settings)
    m.start(0)
    m.tick(None, 20)
    assert m.state == State.ENDING


def test_target_switch_resets_qualification(settings, face):
    m = StateMachine(settings)
    m.tick(face, 0)
    m.tick(face, 0.3)
    m.tick(face.model_copy(update={"track_id": 2}), 3.2)
    assert m.state == State.IDLE and m.facing_since is None
    m.tick(face.model_copy(update={"track_id": 2}), 3.6)
    assert m.state == State.STALKING
    m.tick(face.model_copy(update={"track_id": 2}), 6.7)
    assert m.state == State.AWAKENING


def test_tracking_id_changes_do_not_disconnect_active_session(settings, face):
    m = StateMachine(settings)
    awaken(m, face)
    m.event(ConversationEvent(kind="connected"), 3.4)
    entered = m.entered
    for now, track_id in [(4, 2), (14, 3), (24, 4)]:
        moving = face.model_copy(update={"track_id": track_id, "yaw": 80, "pitch": 50})
        m.tick(moving, now)
        m.event(ConversationEvent(kind="activity"), now)
        assert m.state == State.CONVERSING
        assert m.policy.absent_since is None
        assert m.entered == entered  # Same session, no reconnect/re-awakening.
    m.tick(None, 25)
    m.tick(None, 44.999)
    assert m.state == State.CONVERSING
    m.tick(None, 45)
    assert m.state == State.ENDING and m.reason == "visitor absent"


def test_return_after_occlusion_resets_entire_absence_countdown(settings, face):
    m = StateMachine(settings)
    awaken(m, face)
    m.event(ConversationEvent(kind="connected"), 3.4)
    m.event(ConversationEvent(kind="agent_start"), 4)
    m.tick(None, 5)
    m.tick(face.model_copy(update={"track_id": 99}), 24)
    assert m.state == State.CONVERSING and m.policy.absent_since is None
    m.tick(None, 25)
    m.tick(None, 44.999)
    assert m.state == State.CONVERSING
    m.tick(None, 45)
    assert m.reason == "visitor absent"


def test_repeated_short_tracking_losses_are_not_accumulated(settings, face):
    m = StateMachine(settings)
    awaken(m, face)
    m.event(ConversationEvent(kind="connected"), 3.4)
    for start in (5, 20, 35, 50):
        m.event(ConversationEvent(kind="activity"), start)
        m.tick(None, start)
        m.tick(None, start + 10)
        m.tick(face.model_copy(update={"track_id": int(start)}), start + 11)
        assert m.state == State.CONVERSING and m.policy.absent_since is None


def test_custom_absence_timeout_is_respected(settings, face):
    settings.visitor_absence_timeout_seconds = 30
    m = StateMachine(settings)
    m.start(0)
    m.event(ConversationEvent(kind="connected"), 1)
    m.event(ConversationEvent(kind="agent_start"), 2)
    m.tick(None, 2)
    m.tick(None, 31.999)
    assert m.state == State.CONVERSING
    m.tick(None, 32)
    assert m.state == State.ENDING and m.reason == "visitor absent"


def test_three_second_override_remains_supported(settings, face):
    settings.face_facing_hold_seconds = 3
    m = StateMachine(settings)
    m.tick(face, 0)
    m.tick(face, 0.3)
    m.tick(face, 2.3)
    assert m.state == State.STALKING
    m.tick(face, 3.3)
    assert m.state == State.AWAKENING
