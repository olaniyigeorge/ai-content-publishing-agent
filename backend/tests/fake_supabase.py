"""A minimal in-memory double for the pieces of the supabase-py query
builder this codebase actually uses (table/select/insert/update/delete/eq/
in_/is_/order/limit/execute). Good enough to unit-test service-layer logic
without a live Supabase project or network access.
"""

import uuid
from copy import deepcopy
from datetime import datetime, timezone


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
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def upsert(self, payload):
        self._op = "upsert"
        self._payload = payload
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
            for p in payloads:
                row = deepcopy(p)
                row.setdefault("id", str(uuid.uuid4()))
                row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
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
