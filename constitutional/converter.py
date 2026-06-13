"""Convert Constitutional Court decision XML to Markdown with YAML frontmatter."""

import datetime
import html
import re
import unicodedata
from xml.etree import ElementTree

import yaml

from .config import BODY_SOURCES, PANEL_CODE_MAP

SEP = "_"
MISSING_DATE_SENTINEL = "0000-00-00"
MAX_FILENAME_STEM_BYTES = 180

_FIELDS = [
    "헌재결정례일련번호",
    "종국일자",
    "사건번호",
    "사건명",
    "사건종류명",
    "사건종류코드",
    "재판부구분코드",
    "판시사항",
    "결정요지",
    "전문",
    "참조조문",
    "참조판례",
    "심판대상조문",
]

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \u00A0]{3,}")
_INVALID_PATH_CHARS_RE = re.compile(r"[\x00-\x1f\\/:\0\"'<>|?*]")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class _QuotedStr(str):
    """str subclass that forces single-quoted YAML output."""


class _DecisionDumper(yaml.Dumper):
    """Custom YAML dumper that single-quotes selected string values."""


_DecisionDumper.add_representer(
    _QuotedStr,
    lambda dumper, value: dumper.represent_scalar(
        "tag:yaml.org,2002:str", value, style="'"
    ),
)

_assigned_paths: dict[str, str] = {}


def reset_path_registry() -> None:
    _assigned_paths.clear()


def normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", normalize_nfc(text)).strip()


def html_to_markdown(text: str) -> str:
    text = _BR_RE.sub("\n", text or "")
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def format_date(date_str: str) -> str | None:
    raw = str(date_str or "").strip().replace(".", "").replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        return None
    if raw[:4] in {"0000", "0001"}:
        return None
    try:
        datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _to_date(date_str: str) -> datetime.date | _QuotedStr:
    formatted = format_date(date_str)
    if formatted is None:
        return _QuotedStr(MISSING_DATE_SENTINEL)
    try:
        return datetime.date.fromisoformat(formatted)
    except ValueError:
        return _QuotedStr(formatted)


def panel_name(panel_code: str) -> str:
    code = str(panel_code or "").strip()
    return PANEL_CODE_MAP.get(code, "미분류")


def normalize_case_type(case_type: str) -> str:
    return normalize_text(case_type) or "기타"


def safe_path_part(value: str, *, max_bytes: int = MAX_FILENAME_STEM_BYTES) -> str:
    text = _INVALID_PATH_CHARS_RE.sub(" ", normalize_text(value))
    text = re.sub(r"\s+", " ", text).strip().rstrip(" .")
    while len(text.encode("utf-8")) > max_bytes:
        text = text[:-1].rstrip(" .")
    if not text:
        return "_"
    stem = text.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        text = f"_{text}"
    return text


def sanitize_case_number(case_no: str) -> str:
    value = normalize_text(case_no)
    value = value.replace(", ", "_").replace(",", "_")
    return safe_path_part(value)


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip(" .")


def compose_filename_stem(end_date: str | None, case_no: str, serial: str) -> str:
    date = end_date or MISSING_DATE_SENTINEL
    serial = safe_path_part(str(serial or "_"))
    caseno = sanitize_case_number(case_no) or serial
    prefix = f"{date}{SEP}"
    suffix = f"{SEP}{serial}"
    available = MAX_FILENAME_STEM_BYTES - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    if available <= 0:
        return f"{date}{SEP}{serial}"
    caseno = _truncate_utf8(caseno, available)
    return f"{prefix}{caseno or serial}{suffix}"


def parse_decision_xml(raw_xml: bytes | str) -> dict | None:
    root = ElementTree.fromstring(raw_xml)
    if root.findtext(".//헌재결정례일련번호") is None:
        return None
    return {
        field: normalize_nfc(root.findtext(f".//{field}", "") or "")
        for field in _FIELDS
    }


def compute_decision_path(parsed: dict, *, use_registry: bool = False) -> str:
    serial = str(parsed.get("헌재결정례일련번호", "") or "")
    end_date = format_date(parsed.get("종국일자", "")) or MISSING_DATE_SENTINEL
    case_type = safe_path_part(normalize_case_type(parsed.get("사건종류명", "")))
    panel = safe_path_part(panel_name(parsed.get("재판부구분코드", "")))
    stem = compose_filename_stem(end_date, parsed.get("사건번호", ""), serial)
    path = unicodedata.normalize("NFC", f"{case_type}/{panel}/{stem}.md")
    if not use_registry:
        return path

    existing = _assigned_paths.get(path)
    if existing is None or existing == serial:
        _assigned_paths[path] = serial
        return path

    suffixed = unicodedata.normalize("NFC", f"{case_type}/{panel}/{stem}{SEP}{safe_path_part(serial)}.md")
    _assigned_paths[suffixed] = serial
    return suffixed


def get_decision_path(parsed: dict) -> str:
    return compute_decision_path(parsed, use_registry=True)


def build_frontmatter(parsed: dict) -> dict:
    serial = str(parsed.get("헌재결정례일련번호", ""))
    body_source = parsed.get("본문출처") or "api-text"
    if body_source not in BODY_SOURCES:
        body_source = "api-text"
    return {
        "헌재결정례일련번호": _QuotedStr(serial),
        "사건번호": _QuotedStr(str(parsed.get("사건번호", ""))),
        "사건명": normalize_text(parsed.get("사건명", "")),
        "사건종류": normalize_case_type(parsed.get("사건종류명", "")),
        "사건종류코드": _QuotedStr(str(parsed.get("사건종류코드", ""))),
        "재판부": panel_name(parsed.get("재판부구분코드", "")),
        "재판부구분코드": _QuotedStr(str(parsed.get("재판부구분코드", ""))),
        "종국일자": _to_date(parsed.get("종국일자", "")),
        "본문출처": body_source,
        "출처": f"https://www.law.go.kr/DRF/lawService.do?target=detc&ID={serial}",
        "첨부파일": [],
    }


def decision_to_markdown(parsed: dict) -> str:
    sections = [
        ("판시사항", "판시사항"),
        ("결정요지", "결정요지"),
        ("심판대상조문", "심판대상조문"),
        ("참조조문", "참조조문"),
        ("참조판례", "참조판례"),
        ("전문", "전문"),
    ]
    body_sections: list[str] = []
    for field, heading in sections:
        content = html_to_markdown(parsed.get(field, ""))
        if content:
            body_sections.extend([f"## {heading}", "", content, ""])

    document = dict(parsed)
    if not body_sections:
        document["본문출처"] = "parsing-failed"
        body_sections.extend(["본문은 국가법령정보센터 원문을 참조하세요.", ""])

    frontmatter = build_frontmatter(document)
    yaml_text = yaml.dump(
        frontmatter,
        Dumper=_DecisionDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    title = normalize_text(parsed.get("사건명", "")) or parsed.get("사건번호", "") or parsed.get("헌재결정례일련번호", "")
    body = "\n".join([f"# {title}", "", *body_sections]).rstrip()
    return f"---\n{yaml_text}\n---\n\n{body}\n"
