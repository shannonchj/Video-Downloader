from pathlib import Path

import pytest
from check_forbidden import Finding, main, scan_source


def codes(source: str) -> list[str]:
    return [f.code for f in scan_source(source)]


@pytest.mark.parametrize(
    "source",
    [
        "import os\nos.system('ls')",
        "import os\nos.popen('ls')",
        "import os\nos.execv('/bin/ls', ['ls'])",
        "import os\nos.spawnl(os.P_WAIT, '/bin/ls')",
        "import os as o\no.system('ls')",
        "from os import system\nsystem('ls')",
        "from os import system as run_it\nrun_it('ls')",
        "import subprocess\nsubprocess.getoutput('ls')",
        "import asyncio\nasyncio.create_subprocess_shell('ls')",
        "import os\nos.posix_spawn('/bin/sh', ['sh'], {})",
        "import os\nos.posix_spawnp('sh', ['sh'], {})",
        "import pty\npty.spawn('sh')",
    ],
)
def test_os_shell_calls_are_reported(source: str) -> None:
    assert codes(source) == ["os-system"]


@pytest.mark.parametrize(
    "source",
    [
        "import subprocess\nsubprocess.run(['ls'], shell=True)",
        "import subprocess\nsubprocess.Popen(['ls'], shell=1)",
        "import subprocess\nsubprocess.run(['ls'], shell=flag)",
        "anything(['ls'], shell=True)",
    ],
)
def test_shell_keyword_is_reported(source: str) -> None:
    assert codes(source) == ["shell-true"]


@pytest.mark.parametrize(
    "source",
    [
        "import subprocess\nsubprocess.run('ffmpeg -i in.mp4 out.mp4')",
        "import subprocess\nsubprocess.check_output(f'ffmpeg -i {p}')",
        "import subprocess\nsubprocess.Popen(args='ls -la')",
        "from subprocess import run\nrun('ls')",
        "import subprocess\nsubprocess.run('ffmpeg -i ' + p)",
        "import subprocess\nsubprocess.run(base + ' -i ' + p)",
        "import subprocess\nsubprocess.run('ffmpeg %s' % p)",
        "import subprocess\nsubprocess.run('ffmpeg -i {}'.format(p))",
    ],
)
def test_subprocess_with_string_command_is_reported(source: str) -> None:
    assert codes(source) == ["subprocess-str"]


@pytest.mark.parametrize(
    "source",
    [
        "eval('1 + 1')",
        "exec('x = 1')",
        "import builtins\nbuiltins.eval('1')",
    ],
)
def test_eval_and_exec_builtins_are_reported(source: str) -> None:
    assert codes(source) == ["eval-exec"]


@pytest.mark.parametrize(
    "source",
    [
        "opts = {'exec': 'rm -rf /'}",
        "opts = {'exec_before_download': 'x'}",
        "opts = {'cookiesfrombrowser': ('chrome',)}",
        "opts = {'cookiefile': 'c.txt'}",
        "opts = {'netrc_cmd': 'cat creds'}",
        "opts = {'external_downloader': 'aria2c'}",
        "opts = {'external_downloader_args': ['-x']}",
        "opts = dict(cookiesfrombrowser=('chrome',))",
        "opts['exec'] = 'whoami'",
        "opts = {'postprocessors': [{'exec_cmd': 'whoami'}]}",
        "opts = {'postprocessors': [{'key': 'Exec', 'when': 'after_move'}]}",
        "opts = {'postprocessors': [{'key': 'ExecAfterDownload'}]}",
        "pp = dict(key='Exec')",
    ],
)
def test_forbidden_ytdlp_keys_are_reported(source: str) -> None:
    assert codes(source) == ["ytdlp-key"]


@pytest.mark.parametrize(
    "source",
    [
        "import subprocess\nsubprocess.run(['ffmpeg', '-i', src, dst], check=True)",
        "import subprocess\nsubprocess.run(cmd, shell=False)",
        "from concurrent.futures import ThreadPoolExecutor\nexecutor = ThreadPoolExecutor()",
        "cursor.execute('SELECT 1')",
        "platform.system()",
        "import ast\nast.literal_eval('[1]')",
        "opts = {'format': 'bv*+ba', 'noplaylist': True}",
        "print('exec cookiesfrombrowser shell=True os.system')",
        "def system(x: str) -> None: ...\nsystem('ok')",
        "opts = {'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}]}",
        "sorted(items, key='Exec'.lower)",
        "import subprocess\nsubprocess.run(['ffmpeg', '-i', base + '.mp4'])",
        "from . import subprocess\nsubprocess.run('x')",
        "from .tools import system\nsystem('ok')",
    ],
)
def test_safe_code_is_not_reported(source: str) -> None:
    assert codes(source) == []


def test_finding_carries_filename_and_line() -> None:
    findings = scan_source("x = 1\neval('1')\n", filename="pkg/mod.py")
    assert findings == [
        Finding(path="pkg/mod.py", line=2, code="eval-exec", message=findings[0].message)
    ]
    assert str(findings[0]).startswith("pkg/mod.py:2: eval-exec ")


def test_multiple_findings_are_sorted_by_line() -> None:
    source = "eval('1')\nimport os\nos.system('ls')\n"
    assert [(f.line, f.code) for f in scan_source(source)] == [(1, "eval-exec"), (3, "os-system")]


def test_main_returns_zero_for_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("print('hello')\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 0


def test_main_returns_one_and_prints_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sub = tmp_path / "pkg"
    sub.mkdir()
    bad = sub / "bad.py"
    bad.write_text("import os\nos.system('ls')\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("os.system('ls')\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert out == [f"{bad}:2: os-system call to os.system runs a shell command"]


def test_main_returns_two_on_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def (:\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 2


def test_main_returns_two_for_missing_path(tmp_path: Path) -> None:
    assert main([str(tmp_path / "missing")]) == 2


def test_exec_postprocessor_with_command_reports_both_markers() -> None:
    source = "opts = {'postprocessors': [{'key': 'Exec', 'exec_cmd': 'rm -rf ~'}]}"
    assert codes(source) == ["ytdlp-key", "ytdlp-key"]


def test_main_accepts_utf8_bom(tmp_path: Path) -> None:
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbfimport os\nprint(os.sep)\n")
    assert main([str(tmp_path)]) == 0


def test_main_skips_directories_named_like_python_files(tmp_path: Path) -> None:
    odd = tmp_path / "odd.py"
    odd.mkdir()
    (odd / "inner.py").write_text("print('ok')\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 0


def test_main_returns_two_when_file_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "locked.py").write_text("print('ok')\n", encoding="utf-8")

    def deny(self: Path) -> bytes:
        raise PermissionError(13, "denied", str(self))

    monkeypatch.setattr(Path, "read_bytes", deny)
    assert main([str(tmp_path)]) == 2


def test_parse_error_takes_precedence_over_findings(tmp_path: Path) -> None:
    (tmp_path / "a_bad.py").write_text("eval('1')\n", encoding="utf-8")
    (tmp_path / "b_broken.py").write_text("def (:\n", encoding="utf-8")
    (tmp_path / "c_bad.py").write_text("eval('1')\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 2
