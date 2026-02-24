"""
Telegram bot for Learning Tracker Agent.

기능:
- 사용자가 링크를 보내면 본문을 추출
- Gemini로 요약/인사이트/태그 생성
- Notion DB에 아티클로 저장

실행:
    python telegram_bot.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Optional

import google.generativeai as genai
import trafilatura
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from notion_db import NotionDB

load_dotenv()

URL_PATTERN = re.compile(r"https?://[^\s]+")

SYSTEM_PROMPT = """너는 학습 아티클 정리 도우미다.
입력으로 title, url, article_text를 받으면 아래 JSON만 반환한다.

규칙:
- summary: 한국어 3~5문장, 구체적
- key_insights: 한국어 bullet 3~5개 (줄바꿈으로 구분, 각 줄 '- '로 시작)
- tags: 영어/한글 기술 태그 3~6개 배열
- source: 출처 도메인/매체 (예: arXiv, Medium, GitHub Blog)
- title: 입력 제목이 부실하면 개선해서 60자 이내로 생성

반드시 아래 스키마의 JSON 문자열만 출력:
{
  "title": "...",
  "summary": "...",
  "key_insights": "- ...\\n- ...",
  "tags": ["...", "..."],
  "source": "..."
}
"""


def check_env() -> tuple[bool, list[str]]:
    required = [
        "GEMINI_API_KEY",
        "NOTION_TOKEN",
        "NOTION_DATABASE_ID",
        "TELEGRAM_BOT_TOKEN",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    return (len(missing) == 0, missing)


def extract_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = URL_PATTERN.search(text)
    return m.group(0) if m else None


def fetch_article(url: str) -> tuple[str, str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError("링크에서 본문을 가져오지 못했습니다.")

    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata else ""
    content = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not content:
        raise ValueError("링크 본문 추출에 실패했습니다. (로그인/동적 페이지일 수 있어요)")

    if len(content) > 10000:
        content = content[:10000] + "\n\n[...truncated]"

    return (title or "제목 미상", content)


def summarize_with_gemini(model: genai.GenerativeModel, title: str, url: str, article_text: str) -> dict:
    prompt = (
        f"title: {title}\n"
        f"url: {url}\n"
        f"article_text:\n{article_text}"
    )
    response = model.generate_content(prompt)
    text = (response.text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fenced code block 대응
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 📚\n"
        "링크를 보내주시면 Gemini가 요약하고 Notion에 저장해드려요.\n\n"
        "사용 예시:\n"
        "- https://arxiv.org/abs/2401.00001\n"
        "- 이 글 저장해줘 https://example.com/article"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    url = extract_url(update.message.text)
    if not url:
        await update.message.reply_text("링크를 찾지 못했어요. URL을 포함해서 다시 보내주세요 🙏")
        return

    notion: NotionDB = context.application.bot_data["notion"]
    model: genai.GenerativeModel = context.application.bot_data["model"]

    if notion.url_exists(url):
        await update.message.reply_text("이미 Notion에 저장된 링크예요 ✅")
        return

    status_msg = await update.message.reply_text("링크 분석 중...")

    try:
        title, content = fetch_article(url)
        await status_msg.edit_text("요약 생성 중...")
        structured = summarize_with_gemini(model, title, url, content)

        result = notion.add_article(
            title=structured.get("title", title),
            url=url,
            summary=structured["summary"],
            key_insights=structured["key_insights"],
            tags=structured.get("tags", ["AI"]),
            source=structured.get("source", "Web"),
            status="완료",
        )

        await status_msg.edit_text(
            "저장 완료 ✅\n"
            f"제목: {structured.get('title', title)}\n"
            f"태그: {', '.join(structured.get('tags', []))}\n"
            f"Notion: {result['notion_url']}"
        )
    except Exception as e:
        await status_msg.edit_text(f"처리 중 오류가 발생했어요: {e}")


def main() -> None:
    ok, missing = check_env()
    if not ok:
        print("필수 환경 변수가 없습니다:", ", ".join(missing))
        sys.exit(1)

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    notion = NotionDB()
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    app.bot_data["notion"] = notion
    app.bot_data["model"] = model

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
