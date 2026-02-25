"""Repository-driven ingest pipeline for Learning Tracker.

- Reads URLs / text / PDF files from an input directory.
- Summarizes with selectable LLM provider (gemini/openai/anthropic).
- Stores normalized records into Notion DB.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import trafilatura
from dotenv import load_dotenv
from pypdf import PdfReader

from notion_db import NotionDB

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"]+")

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


@dataclass
class IngestItem:
    title: str
    content: str
    url: str = ""
    source: str = ""


class Provider:
    def summarize(self, title: str, url: str, article_text: str) -> dict:
        raise NotImplementedError


class GeminiProvider(Provider):
    def __init__(self):
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is required for gemini provider")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            system_instruction=SYSTEM_PROMPT,
        )

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        prompt = f"title: {title}\nurl: {url}\narticle_text:\n{article_text}"
        text = (self.model.generate_content(prompt).text or "").strip()
        return parse_json_response(text)


class OpenAIProvider(Provider):
    def __init__(self):
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is required for openai provider")
        self.client = OpenAI(api_key=api_key)
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        prompt = f"title: {title}\nurl: {url}\narticle_text:\n{article_text}"
        resp = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        return parse_json_response(text)


class AnthropicProvider(Provider):
    def __init__(self):
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is required for anthropic provider")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        prompt = f"title: {title}\nurl: {url}\narticle_text:\n{article_text}"
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return parse_json_response("\n".join(text_blocks).strip())


def parse_json_response(text: str) -> dict:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")
    return parsed


def choose_provider(name: str) -> Provider:
    name = name.lower().strip()
    if name == "gemini":
        return GeminiProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "anthropic":
        return AnthropicProvider()
    raise ValueError(f"Unsupported provider: {name}")


def truncate(text: str, limit: int = 10000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n[...truncated]"


def fetch_url_item(url: str) -> IngestItem:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Failed to fetch url: {url}")

    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata else ""
    content = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not content:
        raise ValueError(f"Failed to extract article content: {url}")

    source = "Web"
    if metadata and metadata.sitename:
        source = metadata.sitename

    return IngestItem(title=(title or "제목 미상"), content=truncate(content), url=url, source=source)


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(io.BytesIO(path.read_bytes()))
    pages = [(page.extract_text() or "") for page in reader.pages]
    content = "\n".join(pages).strip()
    if not content:
        raise ValueError(f"No extractable text in PDF: {path}")
    return truncate(content)


def iter_input_items(input_dir: Path) -> Iterable[IngestItem]:
    for file_path in sorted(input_dir.rglob("*")):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            yield IngestItem(
                title=file_path.stem[:60] or "PDF 문서",
                content=extract_pdf_text(file_path),
                source="PDF",
            )
            continue

        if suffix not in {".txt", ".md"}:
            continue

        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        urls = URL_PATTERN.findall(raw)
        if urls:
            for url in urls:
                yield fetch_url_item(url)
            continue

        cleaned = raw.strip()
        if len(cleaned) >= 120:
            title = cleaned.splitlines()[0][:60] or file_path.stem[:60] or "텍스트 메모"
            yield IngestItem(title=title, content=truncate(cleaned), source="Text")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Repository-driven Notion ingest runner")
    parser.add_argument("--input-dir", default="inputs", help="input directory path")
    parser.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "gemini"))
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    provider = choose_provider(args.provider)
    notion = NotionDB()

    processed = 0
    skipped = 0
    failed = 0

    for item in iter_input_items(input_dir):
        try:
            if item.url and notion.url_exists(item.url):
                skipped += 1
                print(f"[SKIP] already exists: {item.url}")
                continue

            structured = provider.summarize(item.title, item.url, item.content)
            res = notion.add_article(
                title=structured.get("title", item.title),
                url=item.url,
                summary=structured["summary"],
                key_insights=structured["key_insights"],
                tags=structured.get("tags", ["AI"]),
                source=structured.get("source", item.source or "Web"),
                status="완료",
            )
            processed += 1
            print(f"[OK] {structured.get('title', item.title)} -> {res['notion_url']}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {item.title}: {exc}")

    print(f"Done. processed={processed}, skipped={skipped}, failed={failed}")
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
