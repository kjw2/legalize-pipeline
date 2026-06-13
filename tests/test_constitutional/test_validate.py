from pathlib import Path

from constitutional.converter import compute_decision_path, decision_to_markdown
from constitutional.validate import validate_markdown_file


def test_validate_markdown_file_accepts_generated_markdown(tmp_path: Path):
    parsed = {
        "헌재결정례일련번호": "58386",
        "종국일자": "20240328",
        "사건번호": "2020헌마123",
        "사건명": "자동차관리법 제26조 등 위헌확인",
        "사건종류명": "헌법소원",
        "사건종류코드": "100",
        "재판부구분코드": "430201",
        "판시사항": "판시사항",
        "결정요지": "결정요지",
        "전문": "전문",
        "참조조문": "",
        "참조판례": "",
        "심판대상조문": "",
    }
    rel = compute_decision_path(parsed)
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text(decision_to_markdown(parsed), encoding="utf-8")

    assert validate_markdown_file(path, repo_root=tmp_path) == []


def test_validate_markdown_file_rejects_path_mismatch(tmp_path: Path):
    path = tmp_path / "헌법소원" / "전원재판부" / "wrong.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        """---
헌재결정례일련번호: '58386'
사건번호: '2020헌마123'
사건명: 자동차관리법 제26조 등 위헌확인
사건종류: 헌법소원
사건종류코드: '100'
재판부: 전원재판부
재판부구분코드: '430201'
종국일자: 2024-03-28
본문출처: api-text
출처: https://www.law.go.kr/DRF/lawService.do?target=detc&ID=58386
첨부파일: []
---

# 본문
""",
        encoding="utf-8",
    )

    errors = validate_markdown_file(path, repo_root=tmp_path)

    assert any("Path mismatch" in error for error in errors)


def test_validate_markdown_file_accepts_missing_end_date_sentinel(tmp_path: Path):
    parsed = {
        "헌재결정례일련번호": "58386",
        "종국일자": "",
        "사건번호": "2020헌마123",
        "사건명": "자동차관리법 제26조 등 위헌확인",
        "사건종류명": "헌법소원",
        "사건종류코드": "100",
        "재판부구분코드": "430201",
        "판시사항": "판시사항",
        "결정요지": "결정요지",
        "전문": "전문",
        "참조조문": "",
        "참조판례": "",
        "심판대상조문": "",
    }
    rel = compute_decision_path(parsed)
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text(decision_to_markdown(parsed), encoding="utf-8")

    assert validate_markdown_file(path, repo_root=tmp_path) == []
