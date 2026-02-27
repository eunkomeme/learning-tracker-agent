"""
Learning Tracker MCP Server

Exposes NotionDB CRUD operations as MCP tools for Claude Code.
Run via stdio transport - never write to stdout inside tool functions.

Registration is handled via .mcp.json at project root.
"""

import json
import os
import sys
from typing import Optional

# Ensure project directory is on the path regardless of CWD at launch time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trafilatura
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from notion_db import NotionDB

load_dotenv()

# ── Server instantiation ──────────────────────────────────────────────────────
mcp = FastMCP(name="learning-tracker")

# ── Lazy NotionDB singleton ───────────────────────────────────────────────────
# Deferred init so the server starts cleanly even if env vars are missing.
# EnvironmentError surfaces at tool call time with a clear message.
_notion: Optional[NotionDB] = None


def get_notion() -> NotionDB:
    global _notion
    if _notion is None:
        _notion = NotionDB()
    return _notion


# ── Tool 1: fetch_article_content ─────────────────────────────────────────────
@mcp.tool()
def fetch_article_content(url: str) -> str:
    """
    Fetch the main text content from a URL.

    Call this BEFORE save_article when a URL is provided.
    Returns up to 8000 characters of extracted text, or an error message.

    Args:
        url: The article URL to fetch and extract text from.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if text:
                if len(text) > 8000:
                    return text[:8000] + "\n\n[... 내용이 너무 길어 앞부분만 가져왔습니다]"
                return text
        return f"URL에서 내용을 가져올 수 없었습니다 ({url}). 직접 내용을 붙여넣어 주세요."
    except Exception as e:
        return f"URL 접근 중 오류 발생: {e}"


# ── Tool 2: save_article ──────────────────────────────────────────────────────
@mcp.tool()
def save_article(
    title: str,
    summary: str,
    key_insights: str,
    tags: list[str],
    url: str = "",
    source: str = "",
    status: str = "완료",
) -> str:
    """
    Save a studied article to the Notion Learning Tracker database.

    Args:
        title: Article title.
        summary: Korean summary of the article (3-5 sentences, specific).
        key_insights: Key insights and learnings (Korean, bullet-point format).
        tags: Relevant tags. Use: AI, LLM, RAG, Agent, Multimodal, Embedding,
              VectorDB, Prompt Engineering, Product, Engineering, Research.
        url: Article URL (optional).
        source: Source name, e.g. arXiv, Medium, GitHub, HuggingFace Blog.
        status: Reading status. One of: 읽을 예정, 읽는 중, 완료. Default: 완료.
    """
    notion = get_notion()
    result = notion.add_article(
        title=title,
        url=url,
        summary=summary,
        key_insights=key_insights,
        tags=tags,
        source=source,
        status=status,
    )
    return json.dumps(
        {
            "success": True,
            "message": "아티클이 노션에 저장되었습니다.",
            "page_id": result["page_id"],
            "notion_url": result["notion_url"],
        },
        ensure_ascii=False,
    )


# ── Tool 3: save_issue ────────────────────────────────────────────────────────
@mcp.tool()
def save_issue(
    title: str,
    description: str,
    suggested_actions: str,
    tags: list[str],
    priority: str = "중간",
    status: str = "대기 중",
) -> str:
    """
    Save an issue or task to the Notion Learning Tracker database.

    Args:
        title: Issue title (clear and concise).
        description: Detailed issue description including problem context and scope.
        suggested_actions: Specific action items to resolve the issue
                           (Korean, bullet-point format).
        tags: Relevant technology/topic tags.
        priority: Issue priority. One of: 높음, 중간, 낮음.
        status: Issue status. One of: 대기 중, 진행 중, 해결됨.
    """
    notion = get_notion()
    result = notion.add_issue(
        title=title,
        description=description,
        suggested_actions=suggested_actions,
        tags=tags,
        priority=priority,
        status=status,
    )
    return json.dumps(
        {
            "success": True,
            "message": "이슈가 노션에 저장되었습니다.",
            "page_id": result["page_id"],
            "notion_url": result["notion_url"],
        },
        ensure_ascii=False,
    )


# ── Tool 4: search_entries ────────────────────────────────────────────────────
@mcp.tool()
def search_entries(
    query: str,
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Search the Notion database by title or tags.

    Args:
        query: Search keyword to match against entry titles and tags.
        type_filter: Filter by entry type. One of: 아티클, 이슈. Omit for all.
        status_filter: Filter by status.
                       Articles: 읽을 예정 | 읽는 중 | 완료
                       Issues:   대기 중 | 진행 중 | 해결됨
        limit: Maximum number of results (default: 10).
    """
    notion = get_notion()
    results = notion.search(
        query=query,
        type_filter=type_filter,
        status_filter=status_filter,
        limit=limit,
    )
    return json.dumps({"count": len(results), "results": results}, ensure_ascii=False)


# ── Tool 5: list_recent_entries ───────────────────────────────────────────────
@mcp.tool()
def list_recent_entries(
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    List the most recently created entries in the Notion database.

    Args:
        type_filter: Filter by entry type. One of: 아티클, 이슈. Omit for all.
        status_filter: Filter by status (same values as search_entries).
        limit: Maximum number of entries to return (default: 20).
    """
    notion = get_notion()
    results = notion.list_recent(
        type_filter=type_filter,
        status_filter=status_filter,
        limit=limit,
    )
    return json.dumps({"count": len(results), "results": results}, ensure_ascii=False)


# ── Tool 6: update_entry_status ───────────────────────────────────────────────
@mcp.tool()
def update_entry_status(page_id: str, status: str, notes: str = "") -> str:
    """
    Update the status of an existing Notion database entry.

    Args:
        page_id: The Notion page ID (from save_article, save_issue, or search results).
        status: New status value.
                Articles: 읽을 예정 | 읽는 중 | 완료
                Issues:   대기 중 | 진행 중 | 해결됨
        notes: Optional notes to append to the entry.
    """
    notion = get_notion()
    result = notion.update_status(page_id=page_id, status=status, notes=notes)
    return json.dumps(
        {
            "success": True,
            "message": f"상태가 '{status}'(으)로 업데이트되었습니다.",
            "page_id": result["page_id"],
            "notion_url": result["notion_url"],
        },
        ensure_ascii=False,
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport
