from app.protocol import FrameParser, make


def test_roundtrip():
    m = make("hello", nickname="alice")
    encoded = m.encode()
    parser = FrameParser()
    msgs = parser.feed(encoded)
    assert len(msgs) == 1
    assert msgs[0].type == "hello"
    assert msgs[0].data == {"nickname": "alice"}


def test_multiple_frames_in_one_chunk():
    a = make("ping").encode()
    b = make("pong", ts=123).encode()
    parser = FrameParser()
    msgs = parser.feed(a + b)
    assert [m.type for m in msgs] == ["ping", "pong"]


def test_partial_frame_buffering():
    data = make("note_updated", note={"id": "x", "content": "hi"}).encode()
    parser = FrameParser()
    # feed one byte at a time
    out = []
    for i in range(len(data)):
        out.extend(parser.feed(data[i : i + 1]))
    assert len(out) == 1
    assert out[0].type == "note_updated"
    assert out[0].data["note"]["id"] == "x"


def test_malformed_frame_dropped():
    parser = FrameParser()
    # length 5, body is garbage that won't decode
    bad = (5).to_bytes(4, "big") + b"\xff\xff\xff\xff\xff"
    msgs = parser.feed(bad)
    assert msgs == []
