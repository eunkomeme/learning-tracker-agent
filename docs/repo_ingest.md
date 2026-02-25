# Repo Ingest 가이드 (Codex/Claude Code)

`repo_ingest.py`를 사용하면 리포지토리의 `inputs/` 폴더에 URL/텍스트/PDF를 넣고, 선택한 LLM provider로 요약 후 Notion DB에 저장할 수 있습니다.

## 입력 준비

- `inputs/*.md`, `inputs/*.txt`: URL 또는 원문 텍스트
- `inputs/*.pdf`: PDF 원문
- `.md/.txt` 파일에 URL이 여러 개 있으면 모두 처리

## 환경 변수

공통:
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

Provider별:
- Gemini: `GEMINI_API_KEY`
- Codex(OpenAI): `OPENAI_API_KEY`
- Claude(Anthropic): `ANTHROPIC_API_KEY`

(선택) 모델 지정:
- `GEMINI_MODEL`
- `OPENAI_MODEL`
- `ANTHROPIC_MODEL`

## 실행

```bash
python repo_ingest.py --source inputs --provider gemini
python repo_ingest.py --source inputs --provider openai
python repo_ingest.py --source inputs --provider anthropic
```

## GitHub Actions 자동 실행

워크플로우: `.github/workflows/repo_ingest.yml`

- 수동 실행: Actions → **Repo Ingest to Notion** → Run workflow
  - `provider`: `gemini|openai|anthropic`
  - `source`: 입력 폴더 경로(기본 `inputs`)
- 정기 실행: 매일 UTC 00:00

필수 GitHub Secrets:
- 공통: `NOTION_TOKEN`, `NOTION_DATABASE_ID`
- Provider별: `GEMINI_API_KEY` 또는 `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY`

## 동작 요약

1. 입력 폴더 스캔(`.txt/.md/.pdf`)
2. URL 본문 추출(`trafilatura`) / PDF 텍스트 추출(`pypdf`)
3. Provider별 구조화 요약(JSON)
4. Notion DB 저장(`notion_db.py`의 `add_article()` 사용)
5. URL 중복 시 자동 skip(`url_exists`)
