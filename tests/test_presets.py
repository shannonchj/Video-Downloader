from collections.abc import Iterator

import pytest
from check_forbidden import FORBIDDEN_POSTPROCESSORS, FORBIDDEN_YTDLP_KEYS

from mediabot.downloader.presets import PRESETS, UnknownPreset, get_preset


def _walk(value: object) -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _walk(item)


def test_m1_presets() -> None:
    assert set(PRESETS) == {"video_mp4", "audio_m4a"}


def test_unknown_preset_raises() -> None:
    with pytest.raises(UnknownPreset) as exc_info:
        get_preset("video_with_subs")
    assert exc_info.value.code == "unknown_preset"


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_presets_contain_no_forbidden_options(name: str) -> None:
    pairs = list(_walk(get_preset(name).build_opts()))
    assert not {k for k, _ in pairs} & FORBIDDEN_YTDLP_KEYS
    assert not {v for k, v in pairs if k == "key"} & FORBIDDEN_POSTPROCESSORS


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_presets_do_not_set_output_or_path_options(name: str) -> None:
    keys = {k for k, _ in _walk(get_preset(name).build_opts())}
    assert not keys & {"outtmpl", "paths", "match_filter", "progress_hooks", "logger"}


def test_build_opts_returns_independent_copy() -> None:
    preset = get_preset("audio_m4a")
    opts = preset.build_opts()
    pps = opts["postprocessors"]
    assert isinstance(pps, list)
    pps.append({"key": "Exec"})
    pps[0]["preferredcodec"] = "mp3"
    assert preset.build_opts()["postprocessors"] == [
        {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
    ]


def test_presets_mapping_is_read_only() -> None:
    with pytest.raises(TypeError):
        PRESETS["evil"] = PRESETS["video_mp4"]
