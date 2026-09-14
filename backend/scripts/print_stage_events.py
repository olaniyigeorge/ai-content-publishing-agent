"""Prints the stage_events trail for one content_request_id, in order.
Usage: python -m scripts.print_stage_events <content_request_id>
"""

import sys

from db.client import get_supabase


def main(request_id: str) -> None:
    db = get_supabase()
    events = (
        db.table("stage_events")
        .select("*")
        .eq("content_request_id", request_id)
        .order("created_at")
        .execute()
        .data
    )
    if not events:
        print(f"no stage_events found for {request_id}")
        return
    for e in events:
        line = f"{e['created_at']}  {e['stage']:<18}  {e['status']:<10}"
        if e.get("detail"):
            line += f"  detail={e['detail']}"
        if e.get("error_message"):
            line += f"  ERROR={e['error_message']}"
        print(line)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.print_stage_events <content_request_id>")
        raise SystemExit(1)
    main(sys.argv[1])
