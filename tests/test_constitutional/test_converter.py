import yaml

from constitutional.converter import (
    compute_decision_path,
    decision_to_markdown,
    parse_decision_xml,
)

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DetcService>
  <헌재결정례일련번호>58386</헌재결정례일련번호>
  <종국일자>20240328</종국일자>
  <사건번호>2020헌마123</사건번호>
  <사건명><![CDATA[자동차관리법 제26조 등 위헌확인]]></사건명>
  <사건종류명>헌법소원</사건종류명>
  <사건종류코드>100</사건종류코드>
  <재판부구분코드>430201</재판부구분코드>
  <판시사항><![CDATA[판시<br/>사항]]></판시사항>
  <결정요지><![CDATA[결정요지 본문]]></결정요지>
  <전문><![CDATA[주문<br/>청구를 기각한다.]]></전문>
  <참조조문><![CDATA[헌법 제10조]]></참조조문>
  <참조판례><![CDATA[헌재 2010헌마1]]></참조판례>
  <심판대상조문><![CDATA[자동차관리법 제26조]]></심판대상조문>
</DetcService>
""".encode("utf-8")


def _frontmatter(markdown: str) -> dict:
    yaml_text = markdown.removeprefix("---\n").split("\n---\n", 1)[0]
    return yaml.safe_load(yaml_text)


def test_parse_decision_xml_returns_fields():
    parsed = parse_decision_xml(SAMPLE_XML)

    assert parsed is not None
    assert parsed["헌재결정례일련번호"] == "58386"
    assert parsed["사건번호"] == "2020헌마123"
    assert parsed["재판부구분코드"] == "430201"


def test_compute_decision_path_uses_detc_grammar():
    parsed = parse_decision_xml(SAMPLE_XML)
    assert parsed is not None

    assert compute_decision_path(parsed) == "헌법소원/전원재판부/2024-03-28_2020헌마123_58386.md"


def test_decision_to_markdown_renders_frontmatter_and_sections():
    parsed = parse_decision_xml(SAMPLE_XML)
    assert parsed is not None

    markdown = decision_to_markdown(parsed)
    fm = _frontmatter(markdown)

    assert fm["헌재결정례일련번호"] == "58386"
    assert fm["재판부"] == "전원재판부"
    assert str(fm["종국일자"]) == "2024-03-28"
    assert "# 자동차관리법 제26조 등 위헌확인" in markdown
    assert "## 결정요지" in markdown
    assert "청구를 기각한다." in markdown


def test_decision_to_markdown_marks_parsing_failed_when_body_empty():
    parsed = parse_decision_xml(SAMPLE_XML)
    assert parsed is not None
    for field in ("판시사항", "결정요지", "전문", "참조조문", "참조판례", "심판대상조문"):
        parsed[field] = ""

    fm = _frontmatter(decision_to_markdown(parsed))

    assert fm["본문출처"] == "parsing-failed"


def test_decision_to_markdown_uses_sentinel_for_missing_end_date():
    parsed = parse_decision_xml(SAMPLE_XML)
    assert parsed is not None
    parsed["종국일자"] = ""

    markdown = decision_to_markdown(parsed)
    fm = _frontmatter(markdown)

    assert fm["종국일자"] == "0000-00-00"
    assert compute_decision_path(parsed) == "헌법소원/전원재판부/0000-00-00_2020헌마123_58386.md"
