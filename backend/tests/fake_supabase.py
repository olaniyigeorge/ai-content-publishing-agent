"""A minimal in-memory double for the pieces of the supabase-py query
builder this codebase actually uses (table/select/insert/update/delete/eq/
in_/is_/order/limit/execute). Good enough to unit-test service-layer logic
without a live Supabase project or network access.
"""

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime

from postgrest.exceptions import APIError

# Mirrors the real Postgres unique constraints that service-layer code
# relies on as a race-condition backstop (e.g. article_drafts_version_unique)
# — without this the fake can't reproduce the exact
# 'duplicate key value violates unique constraint' failure those code paths
# are written to survive, so a regression there would pass in tests and only
# surface against a live Supabase project.
UNIQUE_CONSTRAINTS = {
    "article_drafts": ("content_request_id", "option_label", "version"),
}


def _check_json_serializable(payload):
    """The real supabase-py client json.dumps()'s the payload with no custom
    encoder — a raw datetime/UUID slipping through (e.g. from
    `model.model_dump()` instead of `model.model_dump(mode="json")`) raises
    TypeError there, not here. Do the same check in the fake so that bug
    class is caught by tests instead of only surfacing in production."""
    json.dumps(payload)
    return payload


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store: dict[str, list[dict]], table_name: str):
        self._store = store
        self._table = table_name
        self._filters: list[tuple] = []
        self._op = None
        self._payload = None
        self._order_by: list[tuple[str, bool]] = []
        self._limit = None

    # --- filters ---
    def eq(self, field, value):
        self._filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self._filters.append(("in", field, values))
        return self

    def is_(self, field, value):
        self._filters.append(("is", field, value))
        return self

    def gte(self, field, value):
        self._filters.append(("gte", field, value))
        return self

    def or_(self, expr):
        # Not faithfully implemented — tests that need allowlist matching
        # exercise `_is_allowlisted` via direct monkeypatch instead.
        return self

    def order(self, field, desc=False):
        self._order_by.append((field, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    # --- operations ---
    def select(self, *_args, **_kwargs):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = _check_json_serializable(payload)
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = _check_json_serializable(payload)
        return self

    def upsert(self, payload):
        self._op = "upsert"
        self._payload = _check_json_serializable(payload)
        return self

    def delete(self):
        self._op = "delete"
        return self

    def _rows(self):
        return self._store.setdefault(self._table, [])

    def _matches(self, row):
        for kind, field, value in self._filters:
            if kind == "eq" and row.get(field) != value:
                return False
            if kind == "in" and row.get(field) not in value:
                return False
            if kind == "is" and value == "null" and row.get(field) is not None:
                return False
            if kind == "gte" and (row.get(field) or "") < value:
                return False
        return True

    def execute(self):
        rows = self._rows()
        if self._op == "select":
            matched = [r for r in rows if self._matches(r)]
            for field, desc in reversed(self._order_by):
                matched.sort(key=lambda r: r.get(field) or "", reverse=desc)
            if self._limit:
                matched = matched[: self._limit]
            return _Result(deepcopy(matched))

        if self._op in ("insert", "upsert"):
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            inserted = []
            unique_key = UNIQUE_CONSTRAINTS.get(self._table)
            for p in payloads:
                row = deepcopy(p)
                row.setdefault("id", str(uuid.uuid4()))
                row.setdefault("created_at", datetime.now(UTC).isoformat())
                if self._op == "insert" and unique_key and any(
                    all(r.get(f) == row.get(f) for f in unique_key) for r in rows
                ):
                    raise APIError(
                        {
                            "message": (
                                f'duplicate key value violates unique constraint "{self._table}_version_unique"'
                            ),
                            "code": "23505",
                            "hint": None,
                            "details": (
                                f"Key ({', '.join(unique_key)})="
                                f"({', '.join(str(row.get(f)) for f in unique_key)}) already exists."
                            ),
                        }
                    )
                if self._op == "upsert":
                    existing_idx = next((i for i, r in enumerate(rows) if r.get("id") == row.get("id")), None)
                    if existing_idx is not None:
                        rows[existing_idx] = row
                        inserted.append(row)
                        continue
                rows.append(row)
                inserted.append(row)
            return _Result(deepcopy(inserted))

        if self._op == "update":
            updated = []
            for r in rows:
                if self._matches(r):
                    r.update(deepcopy(self._payload))
                    updated.append(r)
            return _Result(deepcopy(updated))

        if self._op == "delete":
            to_delete = [r for r in rows if self._matches(r)]
            self._store[self._table] = [r for r in rows if r not in to_delete]
            return _Result(deepcopy(to_delete))

        raise AssertionError("no operation set before execute()")


class FakeSupabase:
    """Drop-in for the pieces of supabase.Client this codebase calls."""

    def __init__(self):
        self._store: dict[str, list[dict]] = {}

    def table(self, name: str) -> _Query:
        return _Query(self._store, name)
