# Codex/Claude Code + Notion 자동 요약 (무료 운영 가이드)

Gemini API 고정 구조 대신, **리포지토리 기반 입력(URL/PDF)** + **실행 에이전트(Codex/Claude Code)** + **Notion 저장** 구조로 바꿀 수 있습니다.

## 핵심 결론

- 가능합니다.
- 유료 서버 없이도 GitHub Actions 스케줄러로 정기 실행할 수 있습니다.
- "만료" 이슈는 서버 만료가 아니라 **시크릿/API 키 만료**를 관리하는 문제에 가깝습니다.

## 권장 구조

1. `inputs/` 폴더에 URL 목록(`.txt`/`.md`) 또는 PDF 업로드
2. CI에서 파이썬 스크립트 실행
3. 스크립트가 항목별로 요약 생성
4. Notion DB 저장
5. 처리 완료 항목은 `archive/`로 이동(중복 처리 방지)

## LLM 공급자 전략

`agent.py`에 공급자 인터페이스를 두고 모델을 교체 가능하게 운영합니다.

- `GeminiProvider`
- `OpenAIProvider` (Codex 계열 API 사용 시)
- `AnthropicProvider` (Claude 사용 시)

반환 스키마는 현재 Notion 저장 구조(`title / summary / key_insights / tags / source`)를 유지합니다.

## GitHub Actions로 무료 운영

GitHub-hosted runner를 사용하면 별도 서버 없이 동작합니다.

### 예시 워크플로우

`.github/workflows/notion-ingest.yml`

```yaml
name: notion-ingest

on:
  workflow_dispatch:
  schedule:
    - cron: "0 22 * * *" # KST 07:00

jobs:
  run-ingest:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    concurrency:
      group: notion-ingest
      cancel-in-progress: false

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run ingest
        env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          NOTION_DATABASE_ID: ${{ secrets.NOTION_DATABASE_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          # 또는 OPENAI_API_KEY / ANTHROPIC_API_KEY
        run: |
          python agent.py
```

## 만료/운영 안정성 체크리스트

- API 키를 코드에 넣지 말고 GitHub Secrets 사용
- 토큰 교체 시에도 워크플로우 파일 수정 없이 Secret만 갱신
- Notion 토큰은 보통 자동 만료보다 "수동 폐기" 가능성을 가정하고 운영
- 실패 시 재시도 로직(backoff) 추가 권장
- 중복 저장 방지(`url_exists`) 유지

## Codex/Claude Code 연결 방법

두 방식 중 하나를 선택합니다.

1. **로컬 실행형**: Codex/Claude Code가 리포를 직접 읽고 스크립트를 실행
2. **CI 실행형**: 에이전트는 입력 파일만 커밋하고, 요약/저장은 GitHub Actions가 수행

운영 단순성은 CI 실행형이 가장 높습니다.

## 비용 관점

- 서버 비용: 0원 (GitHub Actions 무료 한도 내)
- 모델 비용: 사용한 API 과금 정책에 따름
- Notion API 자체는 일반적으로 별도 사용료 없이 통합 가능

즉, "유료 서버 없이"는 충분히 가능하고,
실제 비용 포인트는 LLM API 호출량입니다.
