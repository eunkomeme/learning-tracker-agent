"""
뉴스레터 자동 처리 스크립트.

RSS 피드나 이메일 뉴스레터에서 아티클 링크를 자동으로 수집해
Claude로 요약한 뒤 노션에 저장합니다.

사용법:
    python newsletter.py              # RSS + 이메일 전체 처리
    python newsletter.py --rss        # RSS 피드만 처리
    python newsletter.py --email      # 이메일 뉴스레터만 처리
    python newsletter.py --url URL    # 단일 URL 수동 추가

크론탭 예시 (매일 오전 9시 자동 실행):
    0 9 * * * cd /path/to/learning-tracker-agent && python newsletter.py >> newsletter.log 2>&1

환경 변수 (.env):
    RSS_FEEDS              - RSS 피드 URL (쉼표 구분)
    EMAIL_IMAP_SERVER      - IMAP 서버 (예: imap.gmail.com)
    EMAIL_ADDRESS          - 이메일 주소
    EMAIL_APP_PASSWORD     - 앱 비밀번호
    NEWSLETTER_SENDERS     - 뉴스레터 발신자 이메일 (쉼표 구분)
    EMAIL_DAYS_BACK        - 검색 기간 (일, 기본값: 7)
"""

import argparse
import imaplib
import email as email_lib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import google.generativeai as genai
import feedparser
import trafilatura
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from notion_db import NotionDB

load_dotenv()

console = Console()

# 이미 처리한 URL을 추적하는 로컬 파일
PROCESSED_FILE = Path(".processed_urls.json")

# 노션에 저장하지 않을 URL 패턴 (구독취소, 트래킹 파라미터 등)
SKIP_URL_PATTERNS = [
    "unsubscribe", "optout", "opt-out", "mailto:", "tel:",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js",
    "utm_source", "click.sender",
    "twitter.com", "facebook.com", "linkedin.com", "instagram.com",
    "notion.so", "google.com/calendar",
]

# 뉴스레터에서 아티클로 간주할 최소 URL 길이
MIN_URL_LENGTH = 25


# ──────────────────────────────────────────────────────────────────────────────
# URL 중복 추적
# ──────────────────────────────────────────────────────────────────────────────

def load_processed_urls() -> set:
    """로컬 파일에서 처리된 URL 목록을 로드합니다."""
    if PROCESSED_FILE.exists():
        try:
            data = json.loads(PROCESSED_FILE.read_text(encoding="utf-8"))
            return set(data.get("urls", []))
        except Exception:
            return set()
    return set()


def mark_url_processed(url: str):
    """URL을 처리 완료로 기록합니다."""
    existing = load_processed_urls()
    existing.add(url)
    PROCESSED_FILE.write_text(
        json.dumps({"urls": list(existing)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_article_url(url: str) -> bool:
    """뉴스레터 링크가 아티클 URL인지 판단합니다."""
    if not url or len(url) < MIN_URL_LENGTH:
        return False
    if not url.startswith("http"):
        return False
    return not any(pattern in url.lower() for pattern in SKIP_URL_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# 아티클 처리 (Claude 요약 → 노션 저장)
# ──────────────────────────────────────────────────────────────────────────────

def _get_domain(url: str) -> str:
    """URL에서 도메인명을 추출합니다."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


def process_single_article(
    model: genai.GenerativeModel,
    notion: NotionDB,
    url: str,
    hint_title: str = "",
    processed_urls: Optional[set] = None,
) -> bool:
    """
    단일 URL을 처리합니다.
    1. 중복 확인 (로컬 캐시 + 노션 DB)
    2. 내용 추출 (trafilatura)
    3. Claude로 요약/태깅
    4. 노션에 저장
    """
    # 로컬 캐시에서 중복 확인
    if processed_urls and url in processed_urls:
        console.print(f"  [dim]건너뜀 (캐시): {url[:70]}[/dim]")
        return False

    # 노션 DB에서 중복 확인
    if notion.url_exists(url):
        console.print(f"  [dim]건너뜀 (노션에 있음): {url[:70]}[/dim]")
        if processed_urls is not None:
            processed_urls.add(url)
        return False

    # 아티클 내용 추출
    console.print(f"  [dim]내용 가져오는 중: {url[:70]}[/dim]")
    downloaded = trafilatura.fetch_url(url)
    content = ""
    if downloaded:
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        ) or ""

    if not content and not hint_title:
        console.print(f"  [yellow]내용 추출 실패, 건너뜀[/yellow]")
        return False

    # Claude로 요약 생성
    content_block = content[:6000] if content else "(내용을 가져오지 못했습니다)"
    prompt = (
        f"다음 아티클을 분석해서 JSON으로 응답하세요.\n\n"
        f"URL: {url}\n"
        f"힌트 제목: {hint_title or '없음'}\n"
        f"출처: {_get_domain(url)}\n\n"
        f"본문:\n{content_block}\n\n"
        f"반드시 아래 형식의 JSON만 응답하세요 (마크다운 코드블록 없이):\n"
        f'{{\n'
        f'  "title": "아티클 제목 (한국어 또는 영어)",\n'
        f'  "summary": "문제/상황 1~2문장\\n∙ 개념명: 설명\\n∙ 개념명: 설명 (핵심 개념 2~4개)",\n'
        f'  "key_insights": "PM이 꼭 알아야 할 점: 협업·설계 철학 관점 실용 인사이트 2~3단락 (단락 사이 \\n\\n, bullet 아닌 자연스러운 문장)",\n'
        f'  "tags": ["태그1", "태그2"],\n'
        f'  "source": "출처명 (예: yozm IT, Medium, arXiv, 카카오테크블로그)"\n'
        f'}}'
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # JSON 파싱 (코드블록 래핑 제거)
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)

        notion.add_article(
            title=data.get("title", hint_title or url),
            url=url,
            summary=data.get("summary", ""),
            key_insights=data.get("key_insights", ""),
            tags=data.get("tags", []),
            source=data.get("source", _get_domain(url)),
            status="완료",
        )

        mark_url_processed(url)
        if processed_urls is not None:
            processed_urls.add(url)

        console.print(
            f"  [green]✓[/green] {data.get('title', url)[:65]}"
        )
        return True

    except json.JSONDecodeError as e:
        console.print(f"  [red]JSON 파싱 오류: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"  [red]처리 오류: {e}[/red]")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# RSS 피드 처리
# ──────────────────────────────────────────────────────────────────────────────

def process_rss_feeds(
    model: genai.GenerativeModel,
    notion: NotionDB,
    processed_urls: set,
) -> int:
    """RSS 피드를 읽어 새 아티클을 처리합니다."""
    feeds_env = os.environ.get("RSS_FEEDS", "").strip()
    if not feeds_env:
        console.print("[yellow]RSS_FEEDS가 .env에 설정되지 않았습니다.[/yellow]")
        return 0

    feed_urls = [f.strip() for f in feeds_env.split(",") if f.strip()]
    saved = 0

    for feed_url in feed_urls:
        domain = _get_domain(feed_url)
        console.print(f"\n[bold]📡 RSS:[/bold] {domain} ({feed_url})")

        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                console.print(f"  [red]피드 읽기 실패: {feed.bozo_exception}[/red]")
                continue

            entries = feed.entries[:30]  # 최신 30개
            console.print(f"  항목 {len(entries)}개 발견")

            for entry in entries:
                url = entry.get("link", "")
                title = entry.get("title", "")
                if url and is_article_url(url):
                    if process_single_article(model, notion, url, title, processed_urls):
                        saved += 1

        except Exception as e:
            console.print(f"  [red]피드 오류: {e}[/red]")

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# 이메일 뉴스레터 처리 (IMAP)
# ──────────────────────────────────────────────────────────────────────────────

def _decode_email_header(header: str) -> str:
    """이메일 헤더를 디코딩합니다."""
    parts = []
    for decoded, charset in email_lib.header.decode_header(header):
        if isinstance(decoded, bytes):
            parts.append(decoded.decode(charset or "utf-8", errors="ignore"))
        else:
            parts.append(decoded)
    return "".join(parts)


def extract_urls_from_email(msg) -> list:
    """이메일 메시지에서 아티클 URL을 추출합니다."""
    found = []

    for part in msg.walk():
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue

        text = payload.decode("utf-8", errors="ignore")

        if content_type == "text/html":
            soup = BeautifulSoup(text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if is_article_url(href):
                    found.append(href)

        elif content_type == "text/plain":
            pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            for url in re.findall(pattern, text):
                if is_article_url(url):
                    found.append(url)

    # 중복 제거 (순서 유지)
    return list(dict.fromkeys(found))


def process_email_newsletters(
    model: genai.GenerativeModel,
    notion: NotionDB,
    processed_urls: set,
) -> int:
    """IMAP을 통해 이메일 뉴스레터를 읽어 아티클 URL을 처리합니다."""
    imap_server = os.environ.get("EMAIL_IMAP_SERVER", "").strip()
    email_addr = os.environ.get("EMAIL_ADDRESS", "").strip()
    app_password = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
    senders_env = os.environ.get("NEWSLETTER_SENDERS", "").strip()
    days_back = int(os.environ.get("EMAIL_DAYS_BACK", "7"))

    if not all([imap_server, email_addr, app_password]):
        console.print(
            "[yellow]이메일 설정이 없습니다 "
            "(EMAIL_IMAP_SERVER, EMAIL_ADDRESS, EMAIL_APP_PASSWORD).[/yellow]"
        )
        return 0

    senders = [s.strip() for s in senders_env.split(",") if s.strip()]
    if not senders:
        console.print("[yellow]NEWSLETTER_SENDERS가 설정되지 않았습니다.[/yellow]")
        return 0

    saved = 0
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")

    console.print(f"\n[bold]📧 이메일 뉴스레터 처리[/bold] (최근 {days_back}일)")

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_addr, app_password)
        mail.select("INBOX")

        for sender in senders:
            console.print(f"\n  발신자: [cyan]{sender}[/cyan]")

            # IMAP 검색: 특정 발신자 + 날짜 이후
            _, data = mail.search(None, f'FROM "{sender}" SINCE "{since_date}"')
            email_ids = data[0].split() if data[0] else []
            console.print(f"  이메일 {len(email_ids)}개 발견")

            for eid in email_ids:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                raw_msg = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw_msg)

                subject = _decode_email_header(msg.get("Subject", ""))
                console.print(f"\n  📨 {subject[:60]}")

                urls = extract_urls_from_email(msg)
                console.print(f"  URL {len(urls)}개 추출")

                for url in urls:
                    if process_single_article(model, notion, url, "", processed_urls):
                        saved += 1

        mail.logout()

    except imaplib.IMAP4.error as e:
        console.print(f"\n[red]IMAP 오류: {e}[/red]")
        console.print(
            "[dim]Gmail 사용 시 '앱 비밀번호'가 필요합니다. "
            "일반 비밀번호는 동작하지 않습니다.[/dim]"
        )
    except Exception as e:
        console.print(f"\n[red]오류: {e}[/red]")

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="뉴스레터에서 아티클을 자동으로 노션에 저장합니다."
    )
    parser.add_argument("--rss", action="store_true", help="RSS 피드만 처리")
    parser.add_argument("--email", action="store_true", help="이메일 뉴스레터만 처리")
    parser.add_argument("--url", metavar="URL", help="단일 URL 수동 추가")
    args = parser.parse_args()

    # --url, --rss, --email 모두 없으면 전체 실행
    run_all = not any([args.rss, args.email, args.url])

    for var in ["GEMINI_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"]:
        if not os.environ.get(var):
            console.print(f"[red]오류: {var}가 .env에 설정되지 않았습니다.[/red]")
            return

    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash")
    notion = NotionDB()
    processed_urls = load_processed_urls()

    console.print(
        Panel.fit(
            f"[bold]🗞️  뉴스레터 자동 처리[/bold]\n"
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"처리 완료 캐시: {len(processed_urls)}개[/dim]",
            style="blue",
        )
    )

    total = 0

    # 단일 URL 수동 추가
    if args.url:
        console.print(f"\n[bold]🔗 수동 URL 추가[/bold]")
        if process_single_article(model, notion, args.url, "", processed_urls):
            total += 1

    # RSS 피드 처리
    if args.rss or run_all:
        total += process_rss_feeds(model, notion, processed_urls)

    # 이메일 뉴스레터 처리
    if args.email or run_all:
        total += process_email_newsletters(model, notion, processed_urls)

    # 결과 요약
    console.print()
    if total > 0:
        console.print(
            f"[bold green]✅ 완료! 새로 저장된 아티클: {total}개[/bold green]"
        )
    else:
        console.print("[dim]새로 저장된 아티클이 없습니다.[/dim]")

    console.print(
        f"[dim]크론탭 설정: 0 9 * * * cd $(pwd) && python newsletter.py[/dim]"
    )


if __name__ == "__main__":
    main()
