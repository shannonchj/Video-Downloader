"""CLI: python -m mediabot.downloader URL PRESET."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from mediabot.config import get_settings
from mediabot.downloader.presets import PRESETS, UnknownPreset
from mediabot.downloader.runner import DownloadFailed, run
from mediabot.security.urls import InvalidURL, validate_url

log = logging.getLogger("mediabot.downloader")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mediabot.downloader")
    parser.add_argument("url")
    parser.add_argument("preset", help=f"one of: {', '.join(PRESETS)}")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        url = validate_url(args.url)
        result = run(
            url,
            args.preset,
            settings=get_settings(),
            progress_cb=lambda pct: log.debug("progress %.1f%%", pct),
        )
    except (InvalidURL, UnknownPreset) as err:
        log.error("rejected: %s", err.code)
        return 2
    except DownloadFailed as err:
        log.error("download failed: %s", err.code)
        return 1
    log.info("saved %s (%d bytes)", result.path, result.size_bytes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
