"""
Learning Tracker Agent

AI 학습 아티클과 이슈를 노션으로 관리하는 Claude 기반 CLI 에이전트.

사용법:
    python agent.py

환경 변수 설정:
    ANTHROPIC_API_KEY  - Anthropic API 키
    NOTION_TOKEN       - 노션 인테그레이션 토큰
    NOTION_DATABASE_ID - 노션 데이터베이스 ID (setup_notion.py 실행 후 확인)

예시 명령:
    "https://arxiv.org/abs/... 이 논문 정리해줘"
    "RAG 관련해서 검색 품질 이슈가 있어. 한국어 처리가 제대로 안 돼."
    "이번 주 공부한 아티클 보여줘"
    "LLM 관련 이슈 목록 뭐 있어?"
"""

import json
import os
import sys

import anthropic
import trafilatura
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from notion_db import NotionDB

load_dotenv()

console = Console()

# ──────────────────────────────────────────────────────────────────────────────
# 도구 정의
# ──────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "fetch_article_content",
        "description": (
            "URL에서 아티클 내용을 가져옵니다. "
            "URL이 주어졌을 때 아티클을 저장하기 전에 반드시 먼저 호출해 내용을 확인하세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "내용을 가져올 아티클 URL"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "save_article",
        "description": "공부한 아티클을 노션 데이터베이스에 저장합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "아티클 제목"},
                "url": {"type": "string", "description": "아티클 URL (있는 경우)"},
                "summary": {
                    "type": "string",
                    "description": "핵심 내용 한국어 요약 (3~5문장, 구체적으로)",
                },
                "key_insights": {
                    "type": "string",
                    "description": "핵심 인사이트와 배운 점 (한국어, 불릿 포인트 형식)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "관련 기술/주제 태그 (예: AI, LLM, RAG, Agent, Multimodal, "
                        "Embedding, VectorDB, Prompt Engineering, Product, Engineering, Research)"
                    ),
                },
                "source": {
                    "type": "string",
                    "description": "출처 (예: arXiv, Medium, GitHub, HuggingFace Blog)",
                },
                "status": {
                    "type": "string",
                    "enum": ["읽을 예정", "읽는 중", "완료"],
                    "description": "읽기 상태. 지금 저장하는 경우 '완료'로 설정",
                },
            },
            "required": ["title", "summary", "key_insights", "tags"],
        },
    },
    {
        "name": "save_issue",
        "description": "해결해야 할 이슈나 과제를 노션 데이터베이스에 저장합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "이슈 제목 (명확하고 간결하게)"},
                "description": {
                    "type": "string",
                    "description": "이슈 상세 설명 (문제 상황, 영향 범위, 맥락 포함)",
                },
                "suggested_actions": {
                    "type": "string",
                    "description": "해결을 위한 구체적인 액션 아이템 (한국어, 불릿 포인트 형식)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "관련 기술/주제 태그",
                },
                "priority": {
                    "type": "string",
                    "enum": ["높음", "중간", "낮음"],
                    "description": "이슈 우선순위",
                },
                "status": {
                    "type": "string",
                    "enum": ["대기 중", "진행 중", "해결됨"],
                    "description": "이슈 현재 상태 (기본값: 대기 중)",
                },
            },
            "required": ["title", "description", "suggested_actions", "tags", "priority"],
        },
    },
    {
        "name": "search_entries",
        "description": (
            "노션 데이터베이스에서 아티클이나 이슈를 검색합니다. "
            "제목과 태그 기반으로 검색합니다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 키워드 (제목 또는 태그명으로 검색)",
                },
                "type_filter": {
                    "type": "string",
                    "enum": ["아티클", "이슈"],
                    "description": "타입 필터 (생략 시 전체 검색)",
                },
                "status_filter": {
                    "type": "string",
                    "description": (
                        "상태 필터 (아티클: '읽을 예정'|'읽는 중'|'완료', "
                        "이슈: '대기 중'|'진행 중'|'해결됨')"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 결과 수 (기본값: 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_recent_entries",
        "description": "최근 노션 데이터베이스 항목을 나열합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type_filter": {
                    "type": "string",
                    "enum": ["아티클", "이슈"],
                    "description": "타입 필터 (생략 시 전체)",
                },
                "status_filter": {
                    "type": "string",
                    "description": "상태 필터",
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 항목 수 (기본값: 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "update_entry_status",
        "description": "노션 데이터베이스의 특정 항목 상태를 업데이트합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "업데이트할 노션 페이지 ID",
                },
                "status": {"type": "string", "description": "새로운 상태값"},
                "notes": {"type": "string", "description": "추가 메모 (선택사항)"},
            },
            "required": ["page_id", "status"],
        },
    },
]

SYSTEM_PROMPT = """당신은 PM의 학습과 업무를 돕는 AI 어시스턴트입니다.
노션 데이터베이스를 허브로 삼아 AI 관련 아티클과 이슈를 체계적으로 관리합니다.

**주요 역할:**
1. **아티클 저장**: URL이나 아티클 내용이 주어지면, 핵심 내용을 한국어로 요약하고 인사이트를 추출해 노션에 저장
2. **이슈 등록**: 해결해야 할 문제가 주어지면, 구조화하고 액션 아이템을 제안해 저장
3. **검색 및 조회**: 과거 학습 내용이나 이슈를 검색하고 요약

**행동 원칙:**
- URL이 주어지면: fetch_article_content 먼저 호출 → 내용 기반으로 save_article 호출
- 문제/이슈가 언급되면: save_issue로 구조화해 저장
- 조회 요청 시: search_entries 또는 list_recent_entries 사용
- 요약과 인사이트는 항상 한국어로, 명확하고 실용적으로 작성
- 태그는 내용에 맞는 기술/주제 키워드 사용 (AI, LLM, RAG, Agent, Multimodal, Embedding, VectorDB, Prompt Engineering, Product, Engineering, Research 등)
- 저장 완료 후에는 무엇을 저장했는지 간단히 확인 메시지 제공

**응답 스타일:**
- 친근하고 간결하게 응답
- 저장된 내용의 핵심 포인트를 1~2줄로 요약해 제공
- 노션 링크가 있으면 공유"""

# ──────────────────────────────────────────────────────────────────────────────
# 도구 실행 함수
# ──────────────────────────────────────────────────────────────────────────────


def fetch_article_content(url: str) -> str:
    """URL에서 아티클 텍스트를 추출합니다."""
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
                # 컨텍스트 윈도우 절약을 위해 8000자로 제한
                if len(text) > 8000:
                    return text[:8000] + "\n\n[... 내용이 너무 길어 앞부분만 가져왔습니다]"
                return text
        return f"URL에서 내용을 가져올 수 없었습니다 ({url}). 직접 내용을 붙여넣어 주세요."
    except Exception as e:
        return f"URL 접근 중 오류 발생: {e}"


def execute_tool(notion: NotionDB, tool_name: str, tool_input: dict) -> str:
    """도구를 실행하고 결과를 JSON 문자열로 반환합니다."""
    try:
        if tool_name == "fetch_article_content":
            return fetch_article_content(tool_input["url"])

        elif tool_name == "save_article":
            result = notion.add_article(
                title=tool_input["title"],
                url=tool_input.get("url", ""),
                summary=tool_input["summary"],
                key_insights=tool_input["key_insights"],
                tags=tool_input["tags"],
                source=tool_input.get("source", ""),
                status=tool_input.get("status", "완료"),
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

        elif tool_name == "save_issue":
            result = notion.add_issue(
                title=tool_input["title"],
                description=tool_input["description"],
                suggested_actions=tool_input["suggested_actions"],
                tags=tool_input["tags"],
                priority=tool_input.get("priority", "중간"),
                status=tool_input.get("status", "대기 중"),
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

        elif tool_name == "search_entries":
            results = notion.search(
                query=tool_input["query"],
                type_filter=tool_input.get("type_filter"),
                status_filter=tool_input.get("status_filter"),
                limit=tool_input.get("limit", 10),
            )
            return json.dumps(
                {"count": len(results), "results": results},
                ensure_ascii=False,
            )

        elif tool_name == "list_recent_entries":
            results = notion.list_recent(
                type_filter=tool_input.get("type_filter"),
                status_filter=tool_input.get("status_filter"),
                limit=tool_input.get("limit", 20),
            )
            return json.dumps(
                {"count": len(results), "results": results},
                ensure_ascii=False,
            )

        elif tool_name == "update_entry_status":
            result = notion.update_status(
                page_id=tool_input["page_id"],
                status=tool_input["status"],
                notes=tool_input.get("notes", ""),
            )
            return json.dumps(
                {
                    "success": True,
                    "message": f"상태가 '{tool_input['status']}'(으)로 업데이트되었습니다.",
                    "page_id": result["page_id"],
                },
                ensure_ascii=False,
            )

        else:
            return json.dumps(
                {"error": f"알 수 없는 도구: {tool_name}"}, ensure_ascii=False
            )

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# 에이전트 루프
# ──────────────────────────────────────────────────────────────────────────────

TOOL_LABEL = {
    "fetch_article_content": "URL 읽는 중",
    "save_article": "아티클 저장 중",
    "save_issue": "이슈 저장 중",
    "search_entries": "노션 검색 중",
    "list_recent_entries": "목록 불러오는 중",
    "update_entry_status": "상태 업데이트 중",
}


def run_agent_turn(
    client: anthropic.Anthropic,
    notion: NotionDB,
    user_input: str,
    history: list,
) -> list:
    """사용자 입력 한 턴을 처리하고 대화 히스토리를 반환합니다."""
    history.append({"role": "user", "content": user_input})

    console.print()
    console.print("[bold cyan]AI[/bold cyan]: ", end="")

    while True:
        # 스트리밍으로 Claude 응답 수신
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            thinking={"type": "adaptive"},
            messages=history,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
            final_message = stream.get_final_message()

        # 대화 히스토리에 추가 (thinking/tool_use 블록 포함 전체 content)
        history.append({"role": "assistant", "content": final_message.content})

        # 도구 호출이 없으면 종료
        if final_message.stop_reason != "tool_use":
            print()  # 줄바꿈
            break

        # 도구 실행
        tool_results = []
        for block in final_message.content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            label = TOOL_LABEL.get(block.name, block.name)
            console.print(f"\n  [dim italic]→ {label}...[/dim italic]")

            result = execute_tool(notion, block.name, block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
            )

        history.append({"role": "user", "content": tool_results})

        # 도구 결과 반환 후 AI 응답 계속 출력
        print()
        console.print("[bold cyan]AI[/bold cyan]: ", end="")

    return history


# ──────────────────────────────────────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────────────────────────────────────


def check_env() -> bool:
    """필수 환경 변수 확인."""
    missing = []
    for var in ["ANTHROPIC_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"]:
        if not os.environ.get(var):
            missing.append(var)

    if missing:
        console.print(
            Panel.fit(
                f"[bold red]설정 오류[/bold red]\n\n"
                f"다음 환경 변수가 설정되지 않았습니다:\n"
                + "\n".join(f"  • {v}" for v in missing)
                + "\n\n"
                f"[dim].env 파일을 확인하세요.\n"
                f"처음 설정하는 경우: python setup_notion.py[/dim]",
                style="red",
            )
        )
        return False
    return True


def main():
    if not check_env():
        sys.exit(1)

    try:
        notion = NotionDB()
    except EnvironmentError as e:
        console.print(f"[red]오류: {e}[/red]")
        sys.exit(1)

    client = anthropic.Anthropic()

    console.print()
    console.print(
        Panel.fit(
            "[bold]📚 Learning Tracker Agent[/bold]\n\n"
            "AI 학습 아티클과 이슈를 노션으로 관리하세요.\n\n"
            "[dim]예시:\n"
            '  "https://arxiv.org/abs/... 이 논문 정리해줘"\n'
            '  "RAG 검색 품질 이슈가 있어. 한국어 처리가 잘 안 돼."\n'
            '  "이번 주 공부한 아티클 목록 보여줘"\n'
            '  "LLM 관련 미해결 이슈 뭐 있어?"\n\n'
            "  종료: 'q' 또는 Ctrl+C[/dim]",
            style="blue",
        )
    )

    history: list = []

    while True:
        try:
            console.print()
            user_input = console.input("[bold green]You[/bold green]: ").strip()

            if not user_input:
                continue

            if user_input.lower() in {"q", "quit", "exit", "종료"}:
                console.print("\n[dim]안녕히 가세요! 👋[/dim]")
                break

            history = run_agent_turn(client, notion, user_input, history)

        except KeyboardInterrupt:
            console.print("\n[dim]안녕히 가세요! 👋[/dim]")
            break
        except anthropic.APIError as e:
            console.print(f"\n[red]API 오류: {e}[/red]")
        except Exception as e:
            console.print(f"\n[red]오류: {e}[/red]")


if __name__ == "__main__":
    main()
