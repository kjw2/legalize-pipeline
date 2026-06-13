"""Validate Constitutional Court decision Markdown files."""

import datetime
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .config import BODY_SOURCES, PANEL_CODE_MAP
from .converter import MISSING_DATE_SENTINEL, compute_decision_path

REQUIRED_FIELDS = [
    "헌재결정례일련번호",
    "사건번호",
    "사건명",
    "사건종류",
    "사건종류코드",
    "재판부",
    "재판부구분코드",
    "종국일자",
    "본문출처",
    "출처",
    "첨부파일",
]


def _is_law_go_kr_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "law.go.kr" or host.endswith(".law.go.kr")


def _frontmatter_and_body(text: str) -> tuple[dict | None, str, list[str]]:
    if not text.startswith("---\n"):
        return None, "", ["No YAML frontmatter"]
    try:
        yaml_text, body = text[4:].split("\n---\n", 1)
    except ValueError:
        return None, "", ["Unterminated YAML frontmatter"]
    try:
        fm = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return None, "", [f"Invalid YAML: {e}"]
    if not isinstance(fm, dict):
        return None, "", ["Frontmatter is not a dict"]
    return fm, body.strip(), []


def validate_markdown_file(path: Path, *, repo_root: Path) -> list[str]:
    errors: list[str] = []
    rel = path.relative_to(repo_root)
    if unicodedata.normalize("NFC", str(rel)) != str(rel):
        errors.append(f"Path is not NFC-normalized: {rel}")
    if len(rel.parts) != 3 or path.suffix != ".md":
        errors.append(f"Invalid path depth: {rel}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [*errors, f"Cannot read: {e}"]

    fm, body, parse_errors = _frontmatter_and_body(text)
    if parse_errors:
        return errors + parse_errors
    assert fm is not None

    for field in REQUIRED_FIELDS:
        if field not in fm:
            errors.append(f"Missing required field: {field}")

    if fm.get("재판부구분코드") and str(fm.get("재판부구분코드")) in PANEL_CODE_MAP:
        expected_panel = PANEL_CODE_MAP[str(fm.get("재판부구분코드"))]
        if fm.get("재판부") != expected_panel:
            errors.append(f"재판부 mismatch: {fm.get('재판부')} != {expected_panel}")

    end_date = fm.get("종국일자")
    if not isinstance(end_date, datetime.date) and end_date != MISSING_DATE_SENTINEL:
        errors.append(f"종국일자 must be a YAML date or {MISSING_DATE_SENTINEL}")

    if fm.get("본문출처") not in BODY_SOURCES:
        errors.append(f"Invalid 본문출처: {fm.get('본문출처')}")
    if not body:
        errors.append("Body is empty")

    source = str(fm.get("출처", ""))
    if not source or not _is_law_go_kr_url(source):
        errors.append("출처 must be a law.go.kr URL")

    attachments = fm.get("첨부파일") or []
    if not isinstance(attachments, list):
        errors.append("첨부파일 must be a YAML list")

    expected = compute_decision_path({
        "헌재결정례일련번호": str(fm.get("헌재결정례일련번호", "")),
        "종국일자": str(fm.get("종국일자", "")).replace("-", ""),
        "사건번호": str(fm.get("사건번호", "")),
        "사건종류명": str(fm.get("사건종류", "")),
        "재판부구분코드": str(fm.get("재판부구분코드", "")),
    })
    rel_posix = rel.as_posix()
    if rel_posix != expected:
        errors.append(f"Path mismatch: {rel_posix} != {expected}")

    return errors


def main() -> None:
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    errors: list[str] = []
    for md_file in sorted(repo_root.rglob("*.md")):
        rel_parts = md_file.relative_to(repo_root).parts
        if ".git" in md_file.parts or md_file.name in {"README.md", "AGENTS.md"} or rel_parts[0] == "pipeline":
            continue
        errors.extend(f"{md_file}: {error}" for error in validate_markdown_file(md_file, repo_root=repo_root))
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
