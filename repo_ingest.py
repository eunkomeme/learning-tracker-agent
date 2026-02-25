"""Repository-driven ingestion pipeline for Learning Tracker Agent.

사용 예시:
    python repo_ingest.py --source inputs --provider gemini
    python repo_ingest.py --source inputs --provider openai
    python repo_ingest.py --source inputs --provider anthropic

동작:
- source 디렉터리에서 .txt/.md/.pdf 파일을 읽어 URL/텍스트/PDF 입력 수집
- URL은 trafilatura로 본문 추출
- provider(gemini/openai/anthropic)로 구조화 요약 생성
- Notion DB에 article 항목으로 저장
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib import request

import google.generativeai as genai
from pypdf import PdfReader
import trafilatura
from dotenv import load_dotenv

from notion_db import NotionDB

load_dotenv()

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")

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
class InputItem:
    title: str
    url: str
    content: str
    origin: str


class Summarizer:
    def summarize(self, title: str, url: str, article_text: str) -> dict:
        raise NotImplementedError


class GeminiSummarizer(Summarizer):
    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 가 필요합니다.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            system_instruction=SYSTEM_PROMPT,
        )

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        prompt = f"title: {title}\nurl: {url}\narticle_text:\n{article_text}"
        response = self.model.generate_content(prompt)
        return parse_json_response((response.text or "").strip())


class OpenAISummarizer(Summarizer):
    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 가 필요합니다.")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"title: {title}\nurl: {url}\narticle_text:\n{article_text}",
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        req = request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip()
        return parse_json_response(content)


class AnthropicSummarizer(Summarizer):
    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY 가 필요합니다.")
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        payload = {
            "model": self.model,
            "max_tokens": 1200,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"title: {title}\nurl: {url}\narticle_text:\n{article_text}",
                }
            ],
            "temperature": 0.2,
        }
        req = request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = "\n".join(block.get("text", "") for block in data.get("content", []))
        return parse_json_response(content.strip())


def parse_json_response(text: str) -> dict:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed.get("tags"), list):
        parsed["tags"] = ["AI"]
    return parsed


def fetch_article(url: str) -> tuple[str, str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"URL fetch 실패: {url}")

    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata else ""
    content = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not content:
        raise ValueError(f"본문 추출 실패: {url}")

    if len(content) > 10000:
        content = content[:10000] + "\n\n[...truncated]"
    return (title or "제목 미상", content)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [(page.extract_text() or "") for page in reader.pages]
    content = "\n".join(pages).strip()
    if not content:
        raise ValueError("PDF에서 텍스트를 추출하지 못했습니다.")
    if len(content) > 10000:
        content = content[:10000] + "\n\n[...truncated]"
    return content


def collect_from_text_file(path: Path) -> Iterable[InputItem]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    urls = list(dict.fromkeys(URL_PATTERN.findall(raw)))
    for url in urls:
        title, content = fetch_article(url)
        yield InputItem(title=title, url=url, content=content, origin=str(path))

    if not urls and raw.strip():
        cleaned = raw.strip()
        title = cleaned.splitlines()[0][:60] or path.stem
        if len(cleaned) > 10000:
            cleaned = cleaned[:10000] + "\n\n[...truncated]"
        yield InputItem(title=title, url="", content=cleaned, origin=str(path))


def collect_from_pdf(path: Path) -> InputItem:
    content = extract_pdf_text(path.read_bytes())
    return InputItem(title=path.stem[:60] or "PDF 문서", url="", content=content, origin=str(path))


def discover_inputs(source_dir: Path) -> list[InputItem]:
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"source 디렉터리를 찾을 수 없습니다: {source_dir}")

    items: list[InputItem] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md"}:
                items.extend(list(collect_from_text_file(path)))
            elif suffix == ".pdf":
                items.append(collect_from_pdf(path))
        except Exception as e:
            print(f"[WARN] 입력 처리 실패 ({path}): {e}")
    return items


def build_summarizer(provider: str) -> Summarizer:
    if provider == "gemini":
        return GeminiSummarizer()
    if provider == "openai":
        return OpenAISummarizer()
    if provider == "anthropic":
        return AnthropicSummarizer()
    raise ValueError(f"지원하지 않는 provider: {provider}")


def ensure_env(provider: str) -> None:
    required = ["NOTION_TOKEN", "NOTION_DATABASE_ID"]
    if provider == "gemini":
        required.append("GEMINI_API_KEY")
    elif provider == "openai":
        required.append("OPENAI_API_KEY")
    elif provider == "anthropic":
        required.append("ANTHROPIC_API_KEY")

    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise ValueError(f"필수 환경 변수가 없습니다: {', '.join(missing)}")


def run(source: str, provider: str) -> int:
    ensure_env(provider)
    summarizer = build_summarizer(provider)
    notion = NotionDB()

    items = discover_inputs(Path(source))
    if not items:
        print("처리할 입력이 없습니다. (.txt/.md/.pdf)")
        return 0

    success = 0
    for item in items:
        try:
            if item.url and notion.url_exists(item.url):
                print(f"[SKIP] 중복 URL: {item.url}")
                continue

            structured = summarizer.summarize(item.title, item.url, item.content)
            result = notion.add_article(
                title=structured.get("title", item.title),
                url=item.url,
                summary=structured["summary"],
                key_insights=structured["key_insights"],
                tags=structured.get("tags", ["AI"]),
                source=structured.get("source", "Web"),
                status="완료",
            )
            success += 1
            print(f"[OK] {item.origin} -> {result['notion_url']}")
        except Exception as e:
            print(f"[FAIL] {item.origin}: {e}")

    print(f"완료: {success}/{len(items)} 건 저장")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repo input -> LLM 요약 -> Notion 적재")
    parser.add_argument("--source", default="inputs", help="입력 디렉터리 경로 (기본값: inputs)")
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "anthropic"],
        default="gemini",
        help="요약에 사용할 LLM provider",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(run(source=args.source, provider=args.provider))
    except Exception as exc:
        print(f"오류: {exc}")
        sys.exit(1)
