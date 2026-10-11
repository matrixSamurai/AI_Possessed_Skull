import pytest
from malachi.motion.protocol import encode, Framer, parse_reply


def test_partial_and_multiple_packets():
    f = Framer()
    message = encode({"v": 1, "seq": 1, "type": "EYES", "x": 0.2, "y": -0.1})
    assert f.feed(message[:10]) == []
    result = f.feed(message[10:] + encode({"v": 1, "seq": 2, "type": "STOP"}))
    assert len(result) == 2 and result[0].x == 0.2 and result[1].type == "STOP"


@pytest.mark.parametrize("value", [2, float("nan"), float("inf"), ".5"])
def test_reject_invalid_motion(value):
    with pytest.raises(ValueError):
        encode({"seq": 1, "type": "JAW", "open": value})


def test_unknown_version_fields_and_invalid_json():
    for data in [{"v": 2, "seq": 1, "type": "STOP"}, {"seq": 1, "type": "STOP", "pwm": 999}]:
        with pytest.raises(ValueError):
            encode(data)
    with pytest.raises(ValueError):
        Framer().feed(b"oops\n")


def test_oversize_discards_and_recovers():
    f = Framer()
    assert f.feed(b"x" * 500 + b"\n") == []
    assert len(f.feed(encode({"seq": 1, "type": "PING"}))) == 1


def test_ack_validation():
    assert parse_reply(b'{"v":1,"type":"ACK","seq":3}')["seq"] == 3
    with pytest.raises(ValueError):
        parse_reply(b'{"v":9,"type":"ACK","seq":3}')


def test_invalid_frame_recovers_and_duplicate_fields_rejected():
    framer = Framer()
    with pytest.raises(ValueError):
        framer.feed(b"invalid\n")
    assert len(framer.feed(encode({"seq": 1, "type": "PING"}))) == 1
    with pytest.raises(ValueError):
        framer.feed(b'{"v":1,"seq":2,"type":"STOP","type":"RESET"}\n')
