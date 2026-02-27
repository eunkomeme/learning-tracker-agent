# GitHub Actions + Gemini + Notion 자동 요약 (무료 운영 가이드)

**리포지토리 기반 입력(URL/PDF)** + **GitHub Actions 실행** + **Notion 저장** 구조로 무료 운영할 수 있습니다.

## 핵심 결론

- 가능합니다.
- 유료 서버 없이도 GitHub Actions 스케줄러로 정기 실행할 수 있습니다.
- "만료" 이슈는 서버 만료가 아니라 **시크릿/API 키 만료**를 관리하는 문제에 가깝습니다.

## 권장 구조

1. `inputs/` 폴더에 URL 목록(`.txt`/`.md`) 또는 PDF 업로드
2. CI에서 파이썬 스크립트 실행
3. 스크립트가 항목별로 요약 생성
4. Notion DB 저장
5. URL 중복은 `url_exists` 체크로 방지 (파일 아카이브는 운영 정책에 따라 별도 처리)

## LLM 전략 (CI 전용)

`repo_ingest.py`는 Gemini 무료 API를 사용합니다.

- 긴 문서는 청크 단위로 분할(Map) 후 최종 통합(Reduce)
- 429/리소스 제한 시 재시도 + 지수 백오프
- 반환 스키마는 `title / summary / key_insights / tags / source` 유지

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
        run: |
          python repo_ingest.py --input-dir inputs --provider "${LLM_PROVIDER:-gemini}" --provider-chain "${LLM_PROVIDER_CHAIN:-gemini}"
```

## 만료/운영 안정성 체크리스트

- API 키를 코드에 넣지 말고 GitHub Secrets 사용
- 토큰 교체 시에도 워크플로우 파일 수정 없이 Secret만 갱신
- Notion 토큰은 보통 자동 만료보다 "수동 폐기" 가능성을 가정하고 운영
- 실패 시 재시도 로직(backoff) 추가 권장
- 중복 저장 방지(`url_exists`) 유지

## 실행 방식

- **CI 실행형 권장**: 입력 파일 커밋만 하면 GitHub Actions가 요약/저장을 수행
- 로컬 로그인 의존(브라우저/CLI 인증) 구조는 CI에서 동작하지 않으므로 배제

## 비용 관점

- 서버 비용: 0원 (GitHub Actions 무료 한도 내)
- 모델 비용: Gemini API 무료 티어 범위 내 운영 가능 (추가 API 과금 회피)
- Notion API 자체는 일반적으로 별도 사용료 없이 통합 가능

즉, "유료 서버 없이"는 충분히 가능하고,
실제 비용 포인트는 LLM API 호출량입니다.
