import pytest

from mediabot.security.urls import MAX_URL_LEN, InvalidURL, validate_url

VID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={VID}"


@pytest.mark.parametrize(
    "raw",
    [
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtube.com/watch?v={VID}",
        f"https://m.youtube.com/watch?v={VID}",
        f"https://WWW.YouTube.com/watch?v={VID}",
        f"https://www.youtube.com/watch?v={VID}&t=42s&list=PL123",
        f"https://youtu.be/{VID}",
        f"https://youtu.be/{VID}?si=abc",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://youtube.com/shorts/{VID}?feature=share",
    ],
)
def test_accepts_and_canonicalises(raw: str) -> None:
    assert validate_url(raw) == CANONICAL


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (f"http://www.youtube.com/watch?v={VID}", "scheme_or_auth"),
        ("file:///etc/passwd", "scheme_or_auth"),
        ("--exec=whoami", "scheme_or_auth"),
        (f"https://user:pass@youtube.com/watch?v={VID}", "scheme_or_auth"),
        (f"https://user@youtube.com/watch?v={VID}", "scheme_or_auth"),
        (f"https://youtube.com:8443/watch?v={VID}", "bad_port"),
        (f"https://youtube.com:443/watch?v={VID}", "bad_port"),
        (f"https://youtube.com:abc/watch?v={VID}", "bad_port"),
        ("https://127.0.0.1/", "ip_host"),
        ("https://[::1]/", "ip_host"),
        (f"https://10.0.0.1/watch?v={VID}", "ip_host"),
        ("https://evil.com/?v=youtube.com", "host_not_allowed"),
        (f"https://youtube.com.evil.com/watch?v={VID}", "host_not_allowed"),
        (f"https://music.youtube.com/watch?v={VID}", "host_not_allowed"),
        ("https://www.youtube.com/watch?v=short", "bad_video_id"),
        ("https://www.youtube.com/watch", "bad_video_id"),
        ("https://www.youtube.com/shorts/", "bad_video_id"),
        (f"https://youtu.be/{VID};rm", "bad_video_id"),
        (f"https://www.youtube.com/watch?v={VID};rm", "bad_video_id"),
        (f"https://www.youtube.com/watch?v={VID}x", "bad_video_id"),
        ("https://youtu.be/", "bad_video_id"),
        (f"https://youtu.be/{VID}\n", "bad_chars"),
        (f" https://youtu.be/{VID}", "bad_chars"),
        (f"https://youtu.be/{VID} ; whoami", "bad_chars"),
        (f"https://youtu.be/{VID}\x00", "bad_chars"),
        (f"https://you\ttube.com/watch?v={VID}", "bad_chars"),
        (f"https://youtu.be/{VID}​", "bad_chars"),
        ("", "scheme_or_auth"),
    ],
)
def test_rejects_with_code(raw: str, code: str) -> None:
    with pytest.raises(InvalidURL) as exc_info:
        validate_url(raw)
    assert exc_info.value.code == code


def test_rejects_too_long() -> None:
    raw = f"https://www.youtube.com/watch?v={VID}&x=" + "a" * MAX_URL_LEN
    with pytest.raises(InvalidURL) as exc_info:
        validate_url(raw)
    assert exc_info.value.code == "url_too_long"


def test_invalid_url_is_not_a_value_error() -> None:
    assert not issubclass(InvalidURL, ValueError)
