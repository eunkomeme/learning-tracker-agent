"""
노션 Learning Tracker 데이터베이스 초기 설정 스크립트.

실행 방법:
    python setup_notion.py

실행 전 .env 파일에 NOTION_TOKEN이 설정되어 있어야 합니다.
노션 인테그레이션이 부모 페이지에 접근 권한이 있어야 합니다.
"""

import os
import sys
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()


def create_database(notion: Client, parent_page_id: str) -> str:
    """Learning Tracker 노션 데이터베이스를 생성하고 ID를 반환합니다."""
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "📚 Learning Tracker"}}],
        properties={
            "Name": {"title": {}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "아티클", "color": "blue"},
                        {"name": "이슈", "color": "orange"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "읽을 예정", "color": "gray"},
                        {"name": "읽는 중", "color": "yellow"},
                        {"name": "완료", "color": "green"},
                        {"name": "대기 중", "color": "default"},
                        {"name": "진행 중", "color": "blue"},
                        {"name": "해결됨", "color": "green"},
                    ]
                }
            },
            "Priority": {
                "select": {
                    "options": [
                        {"name": "높음", "color": "red"},
                        {"name": "중간", "color": "yellow"},
                        {"name": "낮음", "color": "gray"},
                    ]
                }
            },
            "Tags": {
                "multi_select": {
                    "options": [
                        {"name": "AI", "color": "purple"},
                        {"name": "LLM", "color": "blue"},
                        {"name": "RAG", "color": "green"},
                        {"name": "Agent", "color": "orange"},
                        {"name": "Multimodal", "color": "pink"},
                        {"name": "Embedding", "color": "red"},
                        {"name": "VectorDB", "color": "brown"},
                        {"name": "Prompt Engineering", "color": "yellow"},
                        {"name": "Product", "color": "blue"},
                        {"name": "Engineering", "color": "gray"},
                        {"name": "Research", "color": "purple"},
                        {"name": "Tool Use", "color": "orange"},
                    ]
                }
            },
            "URL": {"url": {}},
            "Source": {"rich_text": {}},
            "Notes": {"rich_text": {}},
        },
    )
    return db["id"]


def main():
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("❌ 오류: NOTION_TOKEN 환경 변수가 설정되지 않았습니다.")
        print(".env 파일에 NOTION_TOKEN을 설정해주세요.")
        sys.exit(1)

    print("=" * 50)
    print("  Learning Tracker 노션 DB 설정")
    print("=" * 50)
    print()
    print("데이터베이스를 생성할 노션 페이지 ID를 입력하세요.")
    print()
    print("페이지 ID 찾는 방법:")
    print("  1. 노션에서 데이터베이스를 넣을 페이지를 엽니다.")
    print("  2. URL을 확인합니다:")
    print("     notion.so/MyWorkspace/PAGE-TITLE-{PAGE_ID}")
    print("  3. URL 마지막 32자리 (하이픈 제외)가 페이지 ID입니다.")
    print()
    print("⚠️  해당 페이지에 노션 인테그레이션이 초대되어 있어야 합니다.")
    print("   (페이지 우상단 ••• → Connections → 인테그레이션 추가)")
    print()

    parent_page_id = input("페이지 ID: ").strip()
    if not parent_page_id:
        print("❌ 오류: 페이지 ID를 입력해주세요.")
        sys.exit(1)

    # 하이픈 제거 (UUID 형식 처리)
    parent_page_id = parent_page_id.replace("-", "").replace(" ", "")

    notion = Client(auth=token)

    print("\n데이터베이스 생성 중...")
    try:
        db_id = create_database(notion, parent_page_id)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n다음을 확인해주세요:")
        print("  1. NOTION_TOKEN이 올바른지 확인")
        print("  2. 노션 인테그레이션이 해당 페이지에 접근 권한이 있는지 확인")
        print("  3. 페이지 ID가 올바른지 확인")
        sys.exit(1)

    print(f"\n✅ 데이터베이스가 성공적으로 생성되었습니다!")
    print()
    print(".env 파일에 다음 줄을 추가하세요:")
    print()
    print(f"  NOTION_DATABASE_ID={db_id}")
    print()
    print("설정 완료 후 agent.py를 실행하세요: python agent.py")


if __name__ == "__main__":
    main()
