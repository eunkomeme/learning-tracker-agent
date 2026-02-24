# Telegram Bot 연동 가이드

## 1) BotFather로 봇 만들기
1. 텔레그램에서 `@BotFather` 검색 후 채팅 시작
2. `/newbot` 입력
3. 봇 이름 입력 (표시 이름)
4. 유저네임 입력 (`...bot`으로 끝나야 함)
5. 발급된 토큰을 복사해서 `.env`의 `TELEGRAM_BOT_TOKEN`에 저장

선택 설정:
- `/setdescription`: 봇 설명
- `/setuserpic`: 프로필 이미지
- `/setcommands`: `start - 봇 사용법 안내`

## 2) 환경 변수 설정
`.env` 파일에 아래 값을 채우세요.

```env
GEMINI_API_KEY=...
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
TELEGRAM_BOT_TOKEN=...
```

## 3) 실행
```bash
pip install -r requirements.txt
python telegram_bot.py
```

## 4) 사용 방법
- URL 전송: 모바일 브라우저/앱에서 아티클 링크를 이 봇에게 공유
- 텍스트 전송: URL 없이 원문 텍스트를 그대로 붙여넣기 (너무 짧으면 거절)
- PDF 전송: 문서를 파일로 업로드하면 텍스트를 추출해 요약
- 요약/인사이트/태그를 Notion DB에 자동 저장

## 5) 문제 해결
- `링크 본문 추출 실패`: 로그인 필요 페이지거나 스크립트 기반 렌더링일 수 있음 → 텍스트/PDF로 보내기
- `PDF 텍스트 추출 실패`: 스캔 이미지 PDF일 수 있음
- `이미 저장된 링크`: 같은 URL이 Notion DB에 존재
- `필수 환경 변수 없음`: `.env` 값 확인
