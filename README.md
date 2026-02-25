# Learning Tracker Agent

> 읽고 싶은 아티클을 저장하면, AI가 자동으로 요약해 Notion 지식 베이스에 정리해 줍니다.
> 서버 비용 0원. GitHub Actions로 매일 자동 실행.

---

## 왜 만들었나

**대상**: 매주 10개 이상의 아티클·논문을 발견하지만, 그것을 체계적으로 쌓지 못하는 지식 노동자.

매일 좋은 아티클, 논문, PDF를 발견하지만 실제로 정리되는 경우는 드물었다.

- **수동 정리**: 시간이 너무 많이 들어 지속하기 어렵다
- **단순 북마크**: 쌓이기만 하고 나중에 검색이 불가능하다
- **유료 서비스 (Readwise 등)**: 비용이 발생하고, 내 Notion 구조와 맞지 않는다

결국 좋은 콘텐츠를 발견해도, 나만의 방식으로 체계적으로 쌓는 시스템이 없었다.

---

## 솔루션

`inputs/` 폴더에 URL, PDF, 텍스트를 넣으면 나머지는 자동으로 처리된다.

1. **저장**: URL 목록(`.txt`) 또는 PDF를 `inputs/` 폴더에 넣는다
2. **요약**: AI가 핵심 내용을 추출하고, 태그와 인사이트를 생성한다
3. **정리**: Notion 데이터베이스에 검색 가능한 형태로 저장된다

GitHub Actions를 통해 매일 자동 실행되므로, 폴더에 파일만 추가하면 된다.

---

## 결과 및 임팩트

<!-- TODO: Notion DB 결과 스크린샷 (태그·요약·인사이트가 채워진 화면) 추가 -->

| 지표 | 결과 |
|------|------|
| 누적 처리 건수 | [N건] |
| 정리 시간 변화 | [주당 N시간 → N분] |
| 중복 저장 발생 | 0건 (URL 중복 방지) |

**정성적 변화**: 북마크에 쌓아두기만 하던 습관에서, 매일 Notion에 자동으로 쌓이는 지식 베이스로 전환됐다. 나중에 찾아보고 싶은 주제를 태그로 검색하면 바로 찾을 수 있다.

---

## 성공 지표 (KPIs)

이 시스템이 "잘 작동하고 있다"고 판단하는 기준:

| 지표 | 목표 | 측정 방법 |
|------|------|---------|
| 요약 정확도 | 핵심 개념 누락 없이 3-5문장 내 요약 | 주관적 샘플 평가 |
| 중복 저장 건수 | 0건 | Notion DB 검사 |
| GitHub Actions 실패율 | < 5% | Actions 로그 |
| 처리 지연 | 입력 후 24시간 이내 Notion 반영 | 커밋 시각 vs. Notion 생성 시각 |

---

## 경쟁사 대비 포지셔닝

| 항목 | Learning Tracker | Readwise | Pocket | Notion Clipper |
|------|-----------------|----------|--------|----------------|
| 비용 | 서버 비용 0원 (기존 구독 활용) | 월 $7.99~ | 무료/유료 | 무료 |
| Notion 연동 | 네이티브 | 제한적 | 없음 | 네이티브 |
| AI 요약 | 커스터마이징 가능 | 자동 하이라이트 | 없음 | 없음 |
| 한국어 요약 | 지원 | 영어 중심 | 없음 | 없음 |
| 오픈소스 | O | X | X | X |

핵심 차별점: Notion을 이미 쓰는 사람이라면, 별도 서비스 없이 AI 요약 + 자동 정리를 기존 구독만으로 구현할 수 있다.

---

## 핵심 제품 결정

### 1. 입력 방식: UI 없는 폴더 기반 설계

Git 커밋 자체가 인풋 트리거가 된다. 별도의 웹 UI나 API 없이 GitHub 레포지토리가 곧 인터페이스다.

- **포기한 것**: 실시간성 (즉각적인 저장 반응)
- **얻은 것**: 인프라 복잡도 0, 별도 서버 불필요
- Telegram 봇(v1)은 실시간 편리하지만 서버가 필요해 보조 채널로만 유지

### 2. LLM 멀티 프로바이더 지원

Gemini, OpenAI, Anthropic 중 하나를 환경변수로 교체할 수 있도록 설계했다.

- **이유**: 특정 API에 종속되지 않고, 비용과 성능을 직접 비교하기 위해
- **트레이드오프**: 구현 복잡도 증가 vs. 공급자 유연성
- 현재 기본값은 `gemini-2.0-flash` (비용 대비 성능 효율)

### 3. URL 중복 방지를 DB 쿼리로 처리

같은 URL이 `inputs/` 폴더에 다시 들어와도 Notion에 중복 저장되지 않는다.

- **방식**: 저장 전 `notion.url_exists(url)`로 검사
- **트레이드오프**: 매 실행마다 Notion API 호출 발생 vs. 이중 저장 방지
- 이중 저장 방지가 더 중요한 가치라 판단, 이 방향을 선택

### 4. GitHub Actions로 무료 스케줄 실행

유료 서버 없이 운영하는 것이 핵심 제약이었다.

- **방식**: cron 스케줄 `0 22 * * *` (KST 기준 매일 07:00) + 수동 실행(`workflow_dispatch`) 병행
- **실제 비용**: GitHub Actions 자체는 무료, LLM API 호출량에서만 비용 발생
- Railway, Heroku 등 유료 서버 대안 검토 후 제외

---

## 작동 방식

```
inputs/ 폴더 (URL 목록 / PDF / 텍스트)
    ↓
repo_ingest.py — 파일 파싱 + 내용 추출
    ↓
LLM Provider — 요약 + 핵심 인사이트 + 태그 생성
    ↓
notion_db.py — 중복 확인 → Notion DB 저장
    ↓
Notion 지식 베이스 (검색 가능)
```

Notion에 저장되는 필드:

| 필드 | 내용 |
|------|------|
| `title` | AI가 생성하거나 개선한 제목 |
| `summary` | 한국어 3-5문장 핵심 요약 |
| `key_insights` | 불릿 형식 핵심 포인트 3-5개 |
| `tags` | 검색용 기술 태그 3-6개 |
| `source` | 출처 매체 (arXiv, Medium, GitHub 등) |

---

## 빠른 시작

**전제 조건**: Python 3.11+, Notion API 토큰, LLM API 키 (Gemini / OpenAI / Anthropic 중 하나)

**설치 및 실행:**

```bash
pip install -r requirements.txt
```

`.env` 파일 설정:

```env
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
LLM_PROVIDER=gemini          # gemini / openai / anthropic
GEMINI_API_KEY=...           # 선택한 공급자의 키만 필요
```

```bash
python repo_ingest.py --input-dir inputs --provider gemini
```

**GitHub Actions 자동화 설정:**

1. `.github/workflows/notion-ingest.yml` 파일이 이미 포함되어 있음
2. GitHub 레포 Settings → Secrets에 아래 값 등록:

| Secret 이름 | 설명 |
|------------|------|
| `NOTION_TOKEN` | Notion 통합 토큰 |
| `NOTION_DATABASE_ID` | 저장할 Notion DB ID |
| `LLM_PROVIDER` | `gemini` / `openai` / `anthropic` |
| `GEMINI_API_KEY` 등 | 선택한 공급자의 API 키 |

---

## Known Limitations & v2 로드맵

### 현재 한계

- **GitHub Actions 실행 한도**: 무료 플랜 월 2,000분 제한 — 대량 처리 시 초과 가능
- **PDF 지원 범위**: 텍스트 기반 PDF만 지원, 스캔 이미지 PDF는 미지원
- **UI 없음**: 파일을 레포에 직접 올려야 하므로 비기술 사용자 접근이 어렵다

### v2 검토 항목

- **브라우저 확장**: 웹 클리퍼로 폴더 접근 없이 브라우저에서 즉시 저장
- **요약 품질 피드백 루프**: Notion에서 요약 평가 → 프롬프트 자동 개선
- **스캔 PDF 지원**: OCR 연동으로 이미지 기반 PDF도 처리

---

## 선택적 통합 기능

**Telegram 봇** — 모바일에서 URL/PDF를 봇에게 전송하면 즉시 Notion에 저장. 실시간 저장이 필요한 경우 활용. Railway 1-클릭 배포 지원. → [`TELEGRAM_BOT.md`](TELEGRAM_BOT.md) 참고

**뉴스레터 자동화** — RSS 피드와 이메일 뉴스레터에서 아티클 링크를 자동 수집. → `newsletter.py` 참고
