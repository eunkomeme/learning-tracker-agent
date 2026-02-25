"""리포지토리의 inputs 폴더(URL/TEXT/PDF)를 읽어 Notion에 저장합니다.

실행 예시:
    python batch_ingest.py --inputs-dir inputs --provider gemini
    python batch_ingest.py --inputs-dir inputs --provider openai --model gpt-5-mini
    python batch_ingest.py --inputs-dir inputs --provider anthropic --model claude-3-5-sonnet-latest
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Optional

import anthropic
import google.generativeai as genai
from openai import OpenAI
from pypdf import PdfReader
import trafilatura

from notion_db import NotionDB

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


class Summarizer:
    def __init__(self, provider: str, model_name: Optional[str] = None):
        self.provider = provider
        self.model_name = model_name

        if provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY 환경 변수가 필요합니다.")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name=model_name or "gemini-2.0-flash",
                system_instruction=SYSTEM_PROMPT,
            )
        elif provider == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다.")
            self.model = OpenAI()
            self.model_name = model_name or "gpt-5-mini"
        elif provider == "anthropic":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY 환경 변수가 필요합니다.")
            self.model = anthropic.Anthropic()
            self.model_name = model_name or "claude-3-5-sonnet-latest"
        else:
            raise ValueError(f"지원하지 않는 provider: {provider}")

    def summarize(self, title: str, url: str, article_text: str) -> dict:
        prompt = f"title: {title}\nurl: {url}\narticle_text:\n{article_text}"
        if self.provider == "gemini":
            response = self.model.generate_content(prompt)
            text = (response.text or "").strip()
        elif self.provider == "openai":
            response = self.model.responses.create(
                model=self.model_name,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            text = (response.output_text or "").strip()
        else:
            response = self.model.messages.create(
                model=self.model_name,
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in response.content if getattr(block, "text", None)
            ).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)


def check_env() -> None:
    required = ["NOTION_TOKEN", "NOTION_DATABASE_ID"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"필수 환경 변수가 없습니다: {', '.join(missing)}")


def fetch_article(url: str) -> tuple[str, str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"링크에서 본문 추출 실패: {url}")

    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata else ""
    content = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not content:
        raise ValueError(f"본문 추출 결과가 비었습니다: {url}")

    if len(content) > 10000:
        content = content[:10000] + "\n\n[...truncated]"

    return (title or "제목 미상", content)


def extract_pdf_text(path: Path) -> str:
    data = path.read_bytes()
    reader = PdfReader(io.BytesIO(data))
    content = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not content:
        raise ValueError(f"PDF 텍스트 추출 실패: {path}")
    if len(content) > 10000:
        content = content[:10000] + "\n\n[...truncated]"
    return content


def parse_text_file(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"빈 텍스트 파일: {path}")

    first_line = text.splitlines()[0].strip()
    if first_line.startswith("http://") or first_line.startswith("https://"):
        title, content = fetch_article(first_line)
        return title, first_line, content

    title = first_line[:60] if first_line else path.stem[:60]
    if len(text) > 10000:
        text = text[:10000] + "\n\n[...truncated]"
    return title or path.stem[:60], "", text


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in {".txt", ".md", ".url", ".pdf"}


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def already_processed(notion: NotionDB, source_url: str, memo_hash: str) -> bool:
    if source_url:
        return notion.url_exists(source_url)
    return bool(notion.search(query=memo_hash, limit=1))


def process_file(notion: NotionDB, summarizer: Summarizer, path: Path) -> Optional[str]:
    if path.suffix.lower() == ".pdf":
        title, url, content = path.stem[:60], "", extract_pdf_text(path)
    else:
        title, url, content = parse_text_file(path)

    memo_hash = text_hash(content)
    if already_processed(notion, url, memo_hash):
        return f"SKIP(중복): {path}"

    structured = summarizer.summarize(title, url, content)
    tags = structured.get("tags", ["AI"])
    tags = tags + [f"repo-hash:{memo_hash}"]

    result = notion.add_article(
        title=structured.get("title", title),
        url=url,
        summary=structured["summary"],
        key_insights=structured["key_insights"],
        tags=tags,
        source=structured.get("source", "Repository Input"),
        status="완료",
    )
    return f"OK: {path} -> {result['notion_url']}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest inputs to Notion")
    parser.add_argument("--inputs-dir", default="inputs", help="URL/TEXT/PDF 입력 폴더")
    parser.add_argument(
        "--provider",
        default="gemini",
        choices=["gemini", "openai", "anthropic"],
        help="요약에 사용할 LLM 공급자",
    )
    parser.add_argument("--model", default=None, help="공급자별 모델명")
    args = parser.parse_args()

    check_env()

    summarizer = Summarizer(provider=args.provider, model_name=args.model)
    notion = NotionDB()

    inputs_dir = Path(args.inputs_dir)
    if not inputs_dir.exists():
        print(f"입력 폴더가 없습니다: {inputs_dir}")
        return

    targets = sorted(p for p in inputs_dir.iterdir() if p.is_file() and is_supported(p))
    if not targets:
        print("처리할 파일이 없습니다.")
        return

    failures = 0
    for path in targets:
        try:
            msg = process_file(notion, summarizer, path)
            print(msg)
        except Exception as exc:
            failures += 1
            print(f"FAIL: {path} - {exc}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
