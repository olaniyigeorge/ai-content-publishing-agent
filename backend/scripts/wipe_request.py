"""Cascade-deletes one content_request_id (honors `on delete cascade`).
Usage: python -m scripts.wipe_request <content_request_id>
"""

import sys

from db.client import get_supabase


def main(request_id: str) -> None:
    db = get_supabase()
    result = db.table("content_requests").delete().eq("id", request_id).execute()
    if not result.data:
        print(f"no content request found with id {request_id}")
        return
    print(f"deleted content_request {request_id} (cascade removed dependent rows)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.wipe_request <content_request_id>")
        raise SystemExit(1)
    main(sys.argv[1])
