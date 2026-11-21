"""Download presets: the only yt-dlp options a user can choose (docs/PLAN.md §7.4, S3)."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from mediabot.errors import MediabotError


class UnknownPreset(MediabotError):
    pass


@dataclass(frozen=True)
class Preset:
    label: str
    opts: Mapping[str, object]

    def build_opts(self) -> dict[str, object]:
        return copy.deepcopy(dict(self.opts))


PRESETS: Mapping[str, Preset] = MappingProxyType(
    {
        "video_mp4": Preset(
            label="影片 MP4（最高 1080p）",
            opts={
                "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
                "merge_output_format": "mp4",
            },
        ),
        "audio_m4a": Preset(
            label="只要音訊 M4A",
            opts={
                "format": "ba[ext=m4a]/ba",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
            },
        ),
    }
)


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError:
        raise UnknownPreset("unknown_preset", name) from None
