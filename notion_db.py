"""
노션 데이터베이스 CRUD 헬퍼 모듈.
Learning Tracker 데이터베이스의 아티클/이슈 항목을 관리합니다.
"""

import os
from typing import Optional
from notion_client import Client


def _to_rich_text(text: str) -> list:
    """텍스트를 노션 rich_text 형식으로 변환합니다. (2000자 제한 처리)"""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = []
    for i in range(0, len(text), 1999):
        chunks.append({"type": "text", "text": {"content": text[i : i + 1999]}})
    return chunks


def _to_page_blocks(summary: str, key_insights: str, item_type: str = "아티클") -> list:
    """Summary와 Key Insights를 노션 페이지 블록으로 변환합니다."""
    blocks = []

    if summary:
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": summary[:2000]}}],
                "icon": {"emoji": "📝"},
                "color": "gray_background",
            },
        })

    if key_insights:
        blocks.append({"object": "block", "type": "divider", "divider": {}})

        label = "주요 인사이트" if item_type == "아티클" else "해결 방안"
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": label}}],
            },
        })

        for line in key_insights.strip().split("\n"):
            text = line.strip().lstrip("-").lstrip("•").strip()
            if text:
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
                    },
                })

    return blocks


def _from_rich_text(prop: dict) -> str:
    """노션 rich_text 속성에서 텍스트를 추출합니다."""
    if prop and prop.get("rich_text"):
        return "".join(t.get("plain_text", "") for t in prop["rich_text"])
    return ""


def _from_title(prop: dict) -> str:
    """노션 title 속성에서 텍스트를 추출합니다."""
    if prop and prop.get("title"):
        return "".join(t.get("plain_text", "") for t in prop["title"])
    return ""


def _from_select(prop: dict) -> str:
    """노션 select 속성에서 값을 추출합니다."""
    if prop and prop.get("select"):
        return prop["select"]["name"]
    return ""


def _from_multi_select(prop: dict) -> list:
    """노션 multi_select 속성에서 값 목록을 추출합니다."""
    if prop and prop.get("multi_select"):
        return [t["name"] for t in prop["multi_select"]]
    return []


def _from_url(prop: dict) -> str:
    """노션 url 속성에서 값을 추출합니다."""
    if prop and prop.get("url"):
        return prop["url"]
    return ""


def _format_page(page: dict) -> dict:
    """노션 페이지 객체를 읽기 쉬운 딕셔너리로 변환합니다."""
    props = page.get("properties", {})
    return {
        "id": page["id"],
        "notion_url": page.get("url", ""),
        "title": _from_title(props.get("Name", {})),
        "type": _from_select(props.get("Type", {})),
        "status": _from_select(props.get("Status", {})),
        "priority": _from_select(props.get("Priority", {})),
        "tags": _from_multi_select(props.get("Tags", {})),
        "url": _from_url(props.get("URL", {})),
        "source": _from_rich_text(props.get("Source", {})),
        "notes": _from_rich_text(props.get("Notes", {})),
        "created_time": page.get("created_time", ""),
    }


class NotionDB:
    """Learning Tracker 노션 데이터베이스 CRUD 클래스."""

    def __init__(self):
        token = os.environ.get("NOTION_TOKEN")
        self.db_id = os.environ.get("NOTION_DATABASE_ID")

        if not token:
            raise EnvironmentError(
                "NOTION_TOKEN 환경 변수가 설정되지 않았습니다. "
                ".env 파일을 확인해주세요."
            )
        if not self.db_id:
            raise EnvironmentError(
                "NOTION_DATABASE_ID 환경 변수가 설정되지 않았습니다. "
                "setup_notion.py를 먼저 실행해주세요."
            )

        # notion-client v3 defaults to Notion-Version "2025-09-03" which removed
        # the /databases/{id}/query endpoint. Pin to 2022-06-28 for compatibility.
        self.client = Client(auth=token, notion_version="2022-06-28")

    def add_article(
        self,
        title: str,
        summary: str,
        key_insights: str,
        tags: list,
        url: str = "",
        source: str = "",
        status: str = "완료",
    ) -> dict:
        """아티클을 데이터베이스에 추가합니다."""
        properties = {
            "Name": {"title": _to_rich_text(title)},
            "Type": {"select": {"name": "아티클"}},
            "Status": {"select": {"name": status}},
            "Tags": {"multi_select": [{"name": tag} for tag in tags]},
        }
        if url:
            properties["URL"] = {"url": url}
        if source:
            properties["Source"] = {"rich_text": _to_rich_text(source)}

        page = self.client.pages.create(
            parent={"database_id": self.db_id},
            properties=properties,
            children=_to_page_blocks(summary, key_insights, "아티클"),
        )
        return {"page_id": page["id"], "notion_url": page["url"]}

    def add_issue(
        self,
        title: str,
        description: str,
        suggested_actions: str,
        tags: list,
        priority: str = "중간",
        status: str = "대기 중",
    ) -> dict:
        """이슈를 데이터베이스에 추가합니다."""
        properties = {
            "Name": {"title": _to_rich_text(title)},
            "Type": {"select": {"name": "이슈"}},
            "Status": {"select": {"name": status}},
            "Priority": {"select": {"name": priority}},
            "Tags": {"multi_select": [{"name": tag} for tag in tags]},
        }

        page = self.client.pages.create(
            parent={"database_id": self.db_id},
            properties=properties,
            children=_to_page_blocks(description, suggested_actions, "이슈"),
        )
        return {"page_id": page["id"], "notion_url": page["url"]}

    def search(
        self,
        query: str,
        type_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """제목과 태그를 기준으로 데이터베이스를 검색합니다."""
        # 제목 또는 태그에서 OR 검색
        search_conditions = [
            {"property": "Name", "title": {"contains": query}},
            {"property": "Tags", "multi_select": {"contains": query}},
        ]
        filter_obj = {"or": search_conditions}

        # 타입/상태 필터를 AND로 결합
        and_conditions = [filter_obj]
        if type_filter:
            and_conditions.append(
                {"property": "Type", "select": {"equals": type_filter}}
            )
        if status_filter:
            and_conditions.append(
                {"property": "Status", "select": {"equals": status_filter}}
            )

        if len(and_conditions) > 1:
            filter_obj = {"and": and_conditions}

        results = self.client.request(
            path=f"databases/{self.db_id}/query",
            method="POST",
            body={
                "filter": filter_obj,
                "page_size": min(limit, 100),
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            },
        )

        return [_format_page(p) for p in results.get("results", [])]

    def list_recent(
        self,
        type_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 20,
    ) -> list:
        """최근 항목을 나열합니다."""
        filter_conditions = []
        if type_filter:
            filter_conditions.append(
                {"property": "Type", "select": {"equals": type_filter}}
            )
        if status_filter:
            filter_conditions.append(
                {"property": "Status", "select": {"equals": status_filter}}
            )

        body: dict = {
            "page_size": min(limit, 100),
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        if len(filter_conditions) == 1:
            body["filter"] = filter_conditions[0]
        elif len(filter_conditions) > 1:
            body["filter"] = {"and": filter_conditions}

        results = self.client.request(
            path=f"databases/{self.db_id}/query",
            method="POST",
            body=body,
        )
        return [_format_page(p) for p in results.get("results", [])]

    def url_exists(self, url: str) -> bool:
        """해당 URL이 이미 데이터베이스에 존재하는지 확인합니다."""
        if not url:
            return False
        try:
            results = self.client.request(
                path=f"databases/{self.db_id}/query",
                method="POST",
                body={"filter": {"property": "URL", "url": {"equals": url}}, "page_size": 1},
            )
            return len(results.get("results", [])) > 0
        except Exception:
            return False

    def update_status(
        self, page_id: str, status: str, notes: str = ""
    ) -> dict:
        """항목의 상태를 업데이트합니다."""
        properties: dict = {"Status": {"select": {"name": status}}}
        if notes:
            properties["Notes"] = {"rich_text": _to_rich_text(notes)}

        page = self.client.pages.update(page_id=page_id, properties=properties)
        return {"page_id": page["id"], "notion_url": page["url"]}
