"""
Learning Tracker Web Server

FastAPI 기반 웹 서버.
모바일 브라우저에서 URL 또는 텍스트를 제출하면
Groq LLM으로 요약 후 Notion 데이터베이스에 저장한다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trafilatura
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from groq import Groq
from pydantic import BaseModel

from notion_db import NotionDB

load_dotenv()

app = FastAPI(title="Learning Tracker")

# ── Lazy singletons ───────────────────────────────────────────────────────────

_notion: NotionDB | None = None
_groq: Groq | None = None


def get_notion() -> NotionDB:
    global _notion
    if _notion is None:
        _notion = NotionDB()
    return _notion


def get_groq() -> Groq:
    global _groq
    if _groq is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY 환경 변수가 설정되지 않았습니다.")
        _groq = Groq(api_key=api_key)
    return _groq


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Learning Tracker">
<title>Learning Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f5f5f7;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 16px;
  }
  .card {
    background: #fff;
    border-radius: 16px;
    padding: 24px;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  }
  h1 {
    font-size: 20px;
    font-weight: 700;
    color: #1d1d1f;
    margin-bottom: 20px;
    text-align: center;
  }
  label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: #6e6e73;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }
  input[type="url"], textarea {
    width: 100%;
    padding: 12px 14px;
    border: 1.5px solid #d1d1d6;
    border-radius: 10px;
    font-size: 16px;
    color: #1d1d1f;
    background: #fafafa;
    outline: none;
    transition: border-color 0.2s;
    margin-bottom: 16px;
    -webkit-appearance: none;
  }
  input[type="url"]:focus, textarea:focus {
    border-color: #0071e3;
    background: #fff;
  }
  textarea { resize: vertical; min-height: 100px; }
  .divider {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    color: #aeaeb2;
    font-size: 13px;
  }
  .divider::before, .divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e5e5ea;
  }
  button {
    width: 100%;
    padding: 14px;
    background: #0071e3;
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, opacity 0.2s;
    -webkit-appearance: none;
  }
  button:disabled { opacity: 0.55; cursor: not-allowed; }
  button:not(:disabled):active { background: #0056b3; }
  #status {
    margin-top: 16px;
    padding: 14px;
    border-radius: 10px;
    font-size: 15px;
    display: none;
    word-break: break-word;
  }
  #status.success { background: #e8f9ef; color: #1a7f37; }
  #status.error   { background: #fff0f0; color: #cf1322; }
  #status a { color: inherit; font-weight: 600; }
  .spinner {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <h1>📚 Learning Tracker</h1>

  <label for="url">URL</label>
  <input type="url" id="url" placeholder="https://..." inputmode="url" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false">

  <div class="divider">또는 텍스트 직접 입력</div>

  <label for="text">본문 텍스트</label>
  <textarea id="text" placeholder="아티클 내용을 붙여넣으세요..."></textarea>

  <button id="btn" onclick="save()">요약해서 저장</button>
  <div id="status"></div>
</div>

<script>
async function save() {
  const url = document.getElementById('url').value.trim();
  const text = document.getElementById('text').value.trim();
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');

  if (!url && !text) {
    showStatus('URL 또는 텍스트를 입력해주세요.', 'error');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>요약 중...';
  status.style.display = 'none';

  try {
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, text })
    });
    const data = await res.json();

    if (data.success) {
      showStatus(
        data.already_exists
          ? '이미 저장된 아티클입니다. <a href="' + data.notion_url + '" target="_blank">Notion에서 보기 →</a>'
          : '✅ 저장 완료! <a href="' + data.notion_url + '" target="_blank">Notion에서 보기 →</a>',
        'success'
      );
      document.getElementById('url').value = '';
      document.getElementById('text').value = '';
    } else {
      showStatus('오류: ' + (data.error || '알 수 없는 오류'), 'error');
    }
  } catch (e) {
    showStatus('네트워크 오류가 발생했습니다.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '요약해서 저장';
  }
}

function showStatus(msg, type) {
  const el = document.getElementById('status');
  el.innerHTML = msg;
  el.className = type;
  el.style.display = 'block';
}

// Enter key on URL field triggers save
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('url').addEventListener('keydown', e => {
    if (e.key === 'Enter') save();
  });
});
</script>
</body>
</html>"""

# ── Summarization prompt ──────────────────────────────────────────────────────

SUMMARIZE_PROMPT = """당신은 PM/개발자를 위한 아티클 요약 전문가입니다.
아래 아티클을 분석해서 반드시 JSON 형식으로만 응답하세요. 설명이나 마크다운 코드블록 없이 순수 JSON만 반환하세요.

{
  "title": "아티클 제목 (한국어 또는 원문 그대로)",
  "summary": "3-5문장 한국어 요약. 핵심 주장과 결론 중심.",
  "key_insights": "• 인사이트1\\n• 인사이트2\\n• 인사이트3",
  "tags": ["태그1", "태그2"],
  "source": "출처 이름 (예: arXiv, Medium, GitHub, HuggingFace Blog)"
}

tags는 다음 중에서만 선택: AI, LLM, RAG, Agent, Multimodal, Embedding, VectorDB, Prompt Engineering, Product, Engineering, Research, Tool Use

아티클:
"""


def _summarize(content: str, url: str = "") -> dict:
    """Groq API로 아티클을 요약한다."""
    client = get_groq()
    text = (content[:8000] if len(content) > 8000 else content)
    if url:
        text = f"URL: {url}\n\n{text}"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": SUMMARIZE_PROMPT + text}
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    raw = response.choices[0].message.content.strip()

    # JSON 파싱 — 가끔 코드블록이 포함될 수 있어서 방어 처리
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── Request / Response models ─────────────────────────────────────────────────

class SaveRequest(BaseModel):
    url: str = ""
    text: str = ""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


@app.post("/api/save")
def api_save(req: SaveRequest):
    url = req.url.strip()
    text = req.text.strip()

    if not url and not text:
        raise HTTPException(status_code=400, detail="url 또는 text 중 하나는 필수입니다.")

    notion = get_notion()

    # 중복 체크
    if url and notion.url_exists(url):
        results = notion.search(query="", type_filter="아티클")
        # URL로 기존 페이지 찾기 (단순 최근 목록에서 확인)
        recent = notion.list_recent(type_filter="아티클", limit=5)
        notion_url = ""
        for item in recent:
            if item.get("url") == url:
                notion_url = item.get("notion_url", "")
                break
        return {"success": True, "already_exists": True, "notion_url": notion_url}

    # URL에서 본문 추출
    content = text
    if url and not content:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if extracted:
                content = extracted

    if not content:
        return {
            "success": False,
            "error": "URL에서 본문을 가져올 수 없습니다. 텍스트를 직접 붙여넣어 주세요.",
        }

    # Groq 요약
    try:
        summary_data = _summarize(content, url=url)
    except Exception as e:
        return {"success": False, "error": f"요약 중 오류: {e}"}

    # Notion 저장
    result = notion.add_article(
        title=summary_data.get("title", "제목 없음"),
        summary=summary_data.get("summary", ""),
        key_insights=summary_data.get("key_insights", ""),
        tags=summary_data.get("tags", []),
        url=url,
        source=summary_data.get("source", ""),
        status="완료",
    )

    return {
        "success": True,
        "already_exists": False,
        "notion_url": result["notion_url"],
        "title": summary_data.get("title", ""),
    }


@app.get("/api/recent")
def api_recent(limit: int = 10):
    notion = get_notion()
    results = notion.list_recent(type_filter="아티클", limit=limit)
    return {"count": len(results), "results": results}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("web_server:app", host="0.0.0.0", port=port, reload=False)
