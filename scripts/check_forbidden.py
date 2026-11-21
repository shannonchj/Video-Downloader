"""Static scan for code patterns forbidden by docs/PLAN.md S3, S4 and S11.

Usage: python scripts/check_forbidden.py [PATH ...]   (default: src)
Exit codes: 0 clean, 1 findings reported, 2 unreadable path or syntax error.

Known limitations, left to code review: dynamically built keys (opts["ex" + "ec"]),
getattr(os, "system"), __import__("os"), command strings stored in a variable before
the call, and **{"shell": True} unpacking.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

SHELL_FUNCS = {
    "os.system",
    "os.popen",
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
    "asyncio.create_subprocess_shell",
}
PROCESS_PREFIXES = ("os.exec", "os.spawn", "os.posix_spawn", "pty.spawn")
SUBPROCESS_FUNCS = {
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
}
EVAL_FUNCS = {"eval", "exec", "builtins.eval", "builtins.exec"}
FORBIDDEN_YTDLP_KEYS = {
    "exec",
    "exec_before_download",
    "exec_cmd",
    "cookiesfrombrowser",
    "cookiefile",
    "external_downloader",
    "external_downloader_args",
}
# yt-dlp's --exec maps to these postprocessor keys in the Python API.
# TODO(M1): verify against yt_dlp/postprocessor/exec.py once yt-dlp is pinned.
FORBIDDEN_POSTPROCESSORS = {"Exec", "ExecAfterDownload"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


def _collect_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    aliases[top] = top
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (f"{node.module}." if node.module else "")
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{prefix}{alias.name}"
    return aliases


def _qualname(node: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _qualname(node.value, aliases)
        return f"{base}.{node.attr}" if base else None
    return None


def _is_string_command(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mod):
        return _is_string_command(node.left) or _is_string_command(node.right)
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        and _is_string_command(node.func.value)
    )


def _is_forbidden_postprocessor(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value in FORBIDDEN_POSTPROCESSORS


def _check_call(node: ast.Call, aliases: dict[str, str]) -> Iterable[tuple[str, str]]:
    name = _qualname(node.func, aliases)
    if name in SHELL_FUNCS:
        yield "os-system", f"call to {name} runs a shell command"
    elif name is not None and name.startswith(PROCESS_PREFIXES):
        yield "os-system", f"call to {name} replaces or spawns a process"
    if name in EVAL_FUNCS:
        yield "eval-exec", f"call to builtin {name.rsplit('.', 1)[-1]}"

    for kw in node.keywords:
        if kw.arg == "shell" and not (
            isinstance(kw.value, ast.Constant) and kw.value.value in (False, None)
        ):
            yield "shell-true", "shell= must be omitted or False; pass an argument list"
        if kw.arg in FORBIDDEN_YTDLP_KEYS:
            yield "ytdlp-key", f"forbidden yt-dlp option {kw.arg!r}"
        if name == "dict" and kw.arg == "key" and _is_forbidden_postprocessor(kw.value):
            yield "ytdlp-key", f"forbidden yt-dlp postprocessor {ast.literal_eval(kw.value)!r}"

    if name in SUBPROCESS_FUNCS:
        command = node.args[0] if node.args else None
        if command is None:
            command = next((kw.value for kw in node.keywords if kw.arg == "args"), None)
        if command is not None and _is_string_command(command):
            yield "subprocess-str", f"{name} with a string command; pass an argument list"


def _forbidden_key(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and node.value in FORBIDDEN_YTDLP_KEYS:
        return str(node.value)
    return None


def scan_source(source: str, filename: str = "<string>") -> list[Finding]:
    """Scan Python source text. Raises SyntaxError if it cannot be parsed."""
    tree = ast.parse(source, filename=filename)
    aliases = _collect_aliases(tree)
    findings: list[Finding] = []

    def add(node: ast.AST, code: str, message: str) -> None:
        findings.append(Finding(filename, getattr(node, "lineno", 0), code, message))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for code, message in _check_call(node, aliases):
                add(node, code, message)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (found := _forbidden_key(key)) is not None:
                    add(key or node, "ytdlp-key", f"forbidden yt-dlp option {found!r}")
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "key"
                    and _is_forbidden_postprocessor(value)
                ):
                    pp = ast.literal_eval(value)
                    add(key, "ytdlp-key", f"forbidden yt-dlp postprocessor {pp!r}")
        elif isinstance(node, ast.Subscript) and (found := _forbidden_key(node.slice)) is not None:
            add(node, "ytdlp-key", f"forbidden yt-dlp option {found!r}")

    findings.sort(key=lambda f: (f.line, f.code))
    return findings


def _iter_python_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.rglob("*.py") if p.is_file())
    return [path]


def main(argv: Sequence[str] | None = None) -> int:
    targets = [Path(p) for p in (argv if argv is not None else sys.argv[1:])] or [Path("src")]
    status = 0
    for target in targets:
        if not target.exists():
            print(f"{target}: path does not exist", file=sys.stderr)
            status = 2
            continue
        for file in _iter_python_files(target):
            try:
                source = file.read_bytes().decode("utf-8-sig")
                findings = scan_source(source, filename=str(file))
            except (OSError, SyntaxError, UnicodeDecodeError) as exc:
                print(f"{file}: cannot scan: {exc}", file=sys.stderr)
                status = 2
                continue
            for finding in findings:
                print(finding)
            if findings and status == 0:
                status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
