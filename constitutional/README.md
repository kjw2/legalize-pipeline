# constitutional — 헌재결정례 데이터 파이프라인

국가법령정보센터 OpenAPI의 헌재결정례(`target=detc`) 데이터를 수집하여
Markdown으로 변환하는 파이프라인입니다.

## CLI

```bash
# 전체 목록 + 상세 XML 캐시
python -m constitutional.fetch_cache

# 캐시를 Markdown으로 변환
python -m constitutional.import_decisions

# Git 커밋까지 생성
python -m constitutional.import_decisions --git

# 최근 14일 증분 업데이트
python -m constitutional.update --days 14 --commit

# 출력 저장소 검증
python -m constitutional.validate "$CONSTITUTIONAL_KR_REPO"
```

## API

| 엔드포인트 | 용도 |
|---|---|
| `lawSearch.do?target=detc` | 헌재결정례 목록 |
| `lawService.do?target=detc&ID={id}` | 헌재결정례 본문 XML |

## 경로

```text
{사건종류}/{재판부}/{종국일자}_{사건번호}_{헌재결정례일련번호}.md
```
