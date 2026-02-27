"""
Learning Tracker Agent

AI 학습 아티클과 이슈를 노션으로 관리하는 Gemini 기반 CLI 에이전트.

사용법:
    python agent.py

환경 변수 설정:
    GEMINI_API_KEY     - Google Gemini API 키 (https://aistudio.google.com 에서 무료 발급)
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

import google.generativeai as genai
from google.generativeai import protos
import trafilatura
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from notion_db import NotionDB

load_dotenv()

console = Console()

# ──────────────────────────────────────────────────────────────────────────────
# 도구 정의 (Gemini protos 형식)
# ──────────────────────────────────────────────────────────────────────────────

GEMINI_TOOLS = protos.Tool(
    function_declarations=[
        protos.FunctionDeclaration(
            name="fetch_article_content",
            description=(
                "URL에서 아티클 내용을 가져옵니다. "
                "URL이 주어졌을 때 아티클을 저장하기 전에 반드시 먼저 호출해 내용을 확인하세요."
            ),
            parameters=protos.Schema(
                type_=protos.Type.OBJECT,
                properties={
                    "url": protos.Schema(
                        type_=protos.Type.STRING,
                        description="내용을 가져올 아티클 URL",
                    )
                },
                required=["url"],
            ),
        ),
        protos.FunctionDeclaration(
            name="save_article",
            description="공부한 아티클을 노션 데이터베이스에 저장합니다.",
            parameters=protos.Schema(
                type_=protos.Type.OBJECT,
                properties={
                    "title": protos.Schema(
                        type_=protos.Type.STRING, description="아티클 제목"
                    ),
                    "url": protos.Schema(
                        type_=protos.Type.STRING, description="아티클 URL (있는 경우)"
                    ),
                    "summary": protos.Schema(
                        type_=protos.Type.STRING,
                        description="문제·해결방향 1~2문장 + 핵심 개념 bullet (∙ 개념명: 설명), 줄바꿈은 \\n으로",
                    ),
                    "key_insights": protos.Schema(
                        type_=protos.Type.STRING,
                        description="PM이 꼭 알아야 할 점: 협업·설계 철학 관점 실용 인사이트 2~3단락, bullet 아닌 자연스러운 문장으로 \\n\\n으로 단락 구분",
                    ),
                    "tags": protos.Schema(
                        type_=protos.Type.ARRAY,
                        items=protos.Schema(type_=protos.Type.STRING),
                        description=(
                            "관련 기술/주제 태그 (예: AI, LLM, RAG, Agent, Multimodal, "
                            "Embedding, VectorDB, Prompt Engineering, Product, Engineering, Research)"
                        ),
                    ),
                    "source": protos.Schema(
                        type_=protos.Type.STRING,
                        description="출처 (예: arXiv, Medium, GitHub, HuggingFace Blog)",
                    ),
                    "status": protos.Schema(
                        type_=protos.Type.STRING,
                        enum=["읽을 예정", "읽는 중", "완료"],
                        description="읽기 상태. 지금 저장하는 경우 '완료'로 설정",
                    ),
                },
                required=["title", "summary", "key_insights", "tags"],
            ),
        ),
        protos.FunctionDeclaration(
            name="save_issue",
            description="해결해야 할 이슈나 과제를 노션 데이터베이스에 저장합니다.",
            parameters=protos.Schema(
                type_=protos.Type.OBJECT,
                properties={
                    "title": protos.Schema(
                        type_=protos.Type.STRING, description="이슈 제목 (명확하고 간결하게)"
                    ),
                    "description": protos.Schema(
                        type_=protos.Type.STRING,
                        description="이슈 상세 설명 (문제 상황, 영향 범위, 맥락 포함)",
                    ),
                    "suggested_actions": protos.Schema(
                        type_=protos.Type.STRING,
                        description="해결을 위한 구체적인 액션 아이템 (한국어, 불릿 포인트 형식)",
                    ),
                    "tags": protos.Schema(
                        type_=protos.Type.ARRAY,
                        items=protos.Schema(type_=protos.Type.STRING),
                        description="관련 기술/주제 태그",
                    ),
                    "priority": protos.Schema(
                        type_=protos.Type.STRING,
                        enum=["높음", "중간", "낮음"],
                        description="이슈 우선순위",
                    ),
                    "status": protos.Schema(
                        type_=protos.Type.STRING,
                        enum=["대기 중", "진행 중", "해결됨"],
                        description="이슈 현재 상태 (기본값: 대기 중)",
                    ),
                },
                required=["title", "description", "suggested_actions", "tags", "priority"],
            ),
        ),
        protos.FunctionDeclaration(
            name="search_entries",
            description=(
                "노션 데이터베이스에서 아티클이나 이슈를 검색합니다. "
                "제목과 태그 기반으로 검색합니다."
            ),
            parameters=protos.Schema(
                type_=protos.Type.OBJECT,
                properties={
                    "query": protos.Schema(
                        type_=protos.Type.STRING,
                        description="검색 키워드 (제목 또는 태그명으로 검색)",
                    ),
                    "type_filter": protos.Schema(
                        type_=protos.Type.STRING,
                        enum=["아티클", "이슈"],
                        description="타입 필터 (생략 시 전체 검색)",
                    ),
                    "status_filter": protos.Schema(
                        type_=protos.Type.STRING,
                        description=(
                            "상태 필터 (아티클: '읽을 예정'|'읽는 중'|'완료', "
                            "이슈: '대기 중'|'진행 중'|'해결됨')"
                        ),
                    ),
                    "limit": protos.Schema(
                        type_=protos.Type.INTEGER, description="최대 결과 수 (기본값: 10)"
                    ),
                },
                required=["query"],
            ),
        ),
        protos.FunctionDeclaration(
            name="list_recent_entries",
            description="최근 노션 데이터베이스 항목을 나열합니다.",
            parameters=protos.Schema(
                type_=protos.Type.OBJECT,
                properties={
                    "type_filter": protos.Schema(
                        type_=protos.Type.STRING,
                        enum=["아티클", "이슈"],
                        description="타입 필터 (생략 시 전체)",
                    ),
                    "status_filter": protos.Schema(
                        type_=protos.Type.STRING, description="상태 필터"
                    ),
                    "limit": protos.Schema(
                        type_=protos.Type.INTEGER, description="최대 항목 수 (기본값: 20)"
                    ),
                },
            ),
        ),
        protos.FunctionDeclaration(
            name="update_entry_status",
            description="노션 데이터베이스의 특정 항목 상태를 업데이트합니다.",
            parameters=protos.Schema(
                type_=protos.Type.OBJECT,
                properties={
                    "page_id": protos.Schema(
                        type_=protos.Type.STRING, description="업데이트할 노션 페이지 ID"
                    ),
                    "status": protos.Schema(
                        type_=protos.Type.STRING, description="새로운 상태값"
                    ),
                    "notes": protos.Schema(
                        type_=protos.Type.STRING, description="추가 메모 (선택사항)"
                    ),
                },
                required=["page_id", "status"],
            ),
        ),
    ]
)

SYSTEM_PROMPT = """당신은 PM의 학습과 업무를 돕는 AI 어시스턴트입니다.
노션 데이터베이스를 허브로 삼아 AI/테크 아티클과 이슈를 체계적으로 관리합니다.

**주요 역할:**
1. **아티클 저장**: URL이나 아티클 내용이 주어지면, 핵심 내용을 PM 관점으로 정리해 노션에 저장
2. **이슈 등록**: 해결해야 할 문제가 주어지면, 구조화하고 액션 아이템을 제안해 저장
3. **검색 및 조회**: 과거 학습 내용이나 이슈를 검색하고 요약

**행동 원칙:**
- URL이 주어지면: fetch_article_content 먼저 호출 → 내용 기반으로 save_article 호출
- 문제/이슈가 언급되면: save_issue로 구조화해 저장
- 조회 요청 시: search_entries 또는 list_recent_entries 사용
- summary: 문제/해결방향 1~2문장 + 핵심 개념 "∙ 개념명: 설명" bullet 2~4개 형식으로
- key_insights: "PM이 꼭 알아야 할 점" — 협업·설계 철학 관점 실용 인사이트 2~3단락 (bullet 아닌 자연스러운 문장, \\n\\n으로 단락 구분)
- tags: 기술 태그 + 아티클 도메인 태그 혼합 (AI, LLM, RAG, Agent, Product, Engineering, Research, 핀테크, 서비스 아키텍처 등)
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
    chat: genai.ChatSession,
    notion: NotionDB,
    user_input: str,
) -> None:
    """사용자 입력 한 턴을 처리합니다. ChatSession이 히스토리를 자동 관리합니다."""
    console.print()
    console.print("[bold cyan]AI[/bold cyan]: ", end="")

    response = chat.send_message(user_input)

    while True:
        # 텍스트 출력
        for part in response.parts:
            if hasattr(part, "text") and part.text:
                print(part.text, end="", flush=True)

        # 함수 호출 확인
        function_calls = [
            part.function_call
            for part in response.parts
            if hasattr(part, "function_call") and part.function_call.name
        ]

        if not function_calls:
            print()
            break

        # 도구 실행
        function_responses = []
        for fn in function_calls:
            label = TOOL_LABEL.get(fn.name, fn.name)
            console.print(f"\n  [dim italic]→ {label}...[/dim italic]")

            result = execute_tool(notion, fn.name, dict(fn.args))
            function_responses.append(
                protos.Part(
                    function_response=protos.FunctionResponse(
                        name=fn.name,
                        response={"result": result},
                    )
                )
            )

        print()
        console.print("[bold cyan]AI[/bold cyan]: ", end="")
        response = chat.send_message(function_responses)


# ──────────────────────────────────────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────────────────────────────────────


def check_env() -> bool:
    """필수 환경 변수 확인."""
    missing = []
    for var in ["GEMINI_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"]:
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
                f"Gemini API 키: https://aistudio.google.com (무료, 카드 불필요)\n"
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

    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=[GEMINI_TOOLS],
        system_instruction=SYSTEM_PROMPT,
    )
    chat = model.start_chat()

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

    while True:
        try:
            console.print()
            user_input = console.input("[bold green]You[/bold green]: ").strip()

            if not user_input:
                continue

            if user_input.lower() in {"q", "quit", "exit", "종료"}:
                console.print("\n[dim]안녕히 가세요! 👋[/dim]")
                break

            run_agent_turn(chat, notion, user_input)

        except KeyboardInterrupt:
            console.print("\n[dim]안녕히 가세요! 👋[/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]오류: {e}[/red]")


if __name__ == "__main__":
    main()
