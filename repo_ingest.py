"""Repository-driven ingest pipeline for Learning Tracker.

- Reads URLs / text / PDF files from an input directory.
- Summarizes with selectable LLM provider (gemini/claude_cli).
- Stores normalized records into Notion DB.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
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

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Provider", "").lower()


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


class ClaudeCliProvider(Provider):
    def __init__(self):
        self.command = os.environ.get("CLAUDE_CLI_COMMAND", "claude")
        self.model = os.environ.get("CLAUDE_CLI_MODEL", "")
        self.timeout_s = int(os.environ.get("CLAUDE_CLI_TIMEOUT_S", "180"))

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"title: {title}\n"
            f"url: {url}\n"
            f"article_text:\n{article_text}\n"
        )
        cmd = [self.command, "-p", prompt]
        if self.model:
            cmd.extend(["--model", self.model])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except FileNotFoundError as exc:
            raise EnvironmentError(
                f"Claude CLI command not found: {self.command}. Install Claude Code CLI first."
            ) from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"claude CLI failed (code={proc.returncode}): {stderr}")

        output = (proc.stdout or "").strip()
        if not output:
            raise RuntimeError("claude CLI returned empty output")
        return parse_json_response(output)


def parse_json_response(text: str) -> dict:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")
    return parsed


def choose_provider(name: str) -> Provider:
    normalized = name.lower().strip()
    if normalized == "gemini":
        return GeminiProvider()
    if normalized == "claude_cli":
        return ClaudeCliProvider()
    raise ValueError(f"Unsupported provider: {name}")


def build_provider_chain(chain: str) -> list[Provider]:
    providers: list[Provider] = []
    for raw_name in [token.strip() for token in chain.split(",") if token.strip()]:
        try:
            providers.append(choose_provider(raw_name))
        except EnvironmentError as exc:
            print(f"[WARN] provider unavailable ({raw_name}): {exc}")
    if not providers:
        raise EnvironmentError(
            "No available providers in chain. Configure GEMINI_API_KEY or Claude CLI."
        )
    return providers


def summarize_with_fallback(
    providers: list[Provider], title: str, url: str, article_text: str
) -> dict:
    last_exc: Exception | None = None
    for provider in providers:
        try:
            result = provider.summarize(title, url, article_text)
            result["_provider"] = provider.name
            return result
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print(f"[WARN] summarize failed on {provider.name}: {exc}")
    raise RuntimeError(f"All providers failed. last_error={last_exc}")


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
    parser.add_argument(
        "--provider",
        default=os.environ.get("LLM_PROVIDER", "auto"),
        help="gemini/claude_cli/auto",
    )
    parser.add_argument(
        "--provider-chain",
        default=os.environ.get("LLM_PROVIDER_CHAIN", "gemini,claude_cli"),
        help="Fallback order when --provider auto is used",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    provider_name = args.provider.lower().strip()
    if provider_name == "auto":
        providers = build_provider_chain(args.provider_chain)
    else:
        providers = [choose_provider(provider_name)]

    provider_label = ", ".join(provider.name for provider in providers)
    print(f"Using provider(s): {provider_label}")
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

            structured = summarize_with_fallback(providers, item.title, item.url, item.content)
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
            used_provider = structured.get("_provider", provider_label)
            print(
                f"[OK] ({used_provider}) {structured.get('title', item.title)} -> {res['notion_url']}"
            )
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {item.title}: {exc}")

    print(f"Done. processed={processed}, skipped={skipped}, failed={failed}")
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
