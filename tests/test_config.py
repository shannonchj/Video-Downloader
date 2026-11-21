from pathlib import Path

import pytest
from pydantic import ValidationError

from mediabot.config import Settings


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("VAULT_DIR", "MAX_FILESIZE_BYTES", "MAX_DURATION_SECONDS"):
        monkeypatch.delenv(name, raising=False)


def test_vault_dir_is_required() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_and_derived_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VAULT_DIR", str(tmp_path))
    s = Settings(_env_file=None)
    assert s.download_dir == tmp_path / "downloads"
    assert s.work_dir == tmp_path / "work"
    assert s.max_filesize_bytes == 4 * 1024**3
    assert s.max_duration_seconds == 10800


def test_limits_read_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VAULT_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_FILESIZE_BYTES", "1024")
    monkeypatch.setenv("MAX_DURATION_SECONDS", "60")
    s = Settings(_env_file=None)
    assert s.max_filesize_bytes == 1024
    assert s.max_duration_seconds == 60


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_limits_must_be_positive_int(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    monkeypatch.setenv("VAULT_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_DURATION_SECONDS", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_unrelated_env_vars_are_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(f"VAULT_DIR={tmp_path}\nMODE=standalone\nLINK_TTL_SECONDS=86400\n")
    s = Settings(_env_file=env_file)
    assert s.vault_dir == tmp_path
