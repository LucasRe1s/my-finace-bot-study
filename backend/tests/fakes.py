"""Supabase em memoria para testes de servicos com varias queries encadeadas,
onde mocks de cadeia (table().select().eq()...) ficam ilegiveis. Cobre so o
subconjunto da API usado no projeto."""
from uuid import uuid4


class UniqueViolation(Exception):
    pass


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self._db = db
        self._table = table
        self._filters = []
        self._op = "select"
        self._payload = None
        self._on_conflict = None
        self._single = False
        self._limit = None

    def select(self, *_args):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def upsert(self, payload, on_conflict="id"):
        self._op, self._payload, self._on_conflict = "upsert", payload, on_conflict
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, column, value):
        self._filters.append(lambda row: row.get(column) == value)
        return self

    def is_(self, column, value):
        assert value == "null", "FakeSupabase so suporta is_(col, 'null')"
        self._filters.append(lambda row: row.get(column) is None)
        return self

    def gte(self, column, value):
        self._filters.append(lambda row: row.get(column) is not None and row[column] >= value)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])
        matched = [row for row in rows if all(f(row) for f in self._filters)]

        if self._op == "select":
            data = [dict(row) for row in matched][: self._limit]
            if self._single:
                return _Result(data[0]) if data else None
            return _Result(data)

        if self._op == "insert":
            items = self._payload if isinstance(self._payload, list) else [self._payload]
            created = []
            for item in items:
                row = {"id": str(uuid4()), **item}
                self._db.check_unique(self._table, row)
                rows.append(row)
                created.append(dict(row))
            return _Result(created)

        if self._op == "update":
            for row in matched:
                self._db.check_unique(self._table, {**row, **self._payload}, ignore=row)
                row.update(self._payload)
            return _Result([dict(row) for row in matched])

        if self._op == "upsert":
            key = self._on_conflict
            existing = next((row for row in rows if row.get(key) == self._payload.get(key)), None)
            if existing:
                existing.update(self._payload)
                return _Result([dict(existing)])
            row = {"id": str(uuid4()), **self._payload}
            rows.append(row)
            return _Result([dict(row)])

        if self._op == "delete":
            for row in matched:
                rows.remove(row)
            return _Result([dict(row) for row in matched])

        raise AssertionError(f"operacao desconhecida: {self._op}")


class FakeSupabase:
    def __init__(self, unique: dict[str, list[tuple[str, ...]]] | None = None):
        self.tables: dict[str, list[dict]] = {}
        self._unique = unique or {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def check_unique(self, table: str, candidate: dict, ignore: dict | None = None) -> None:
        for columns in self._unique.get(table, []):
            key = tuple(candidate.get(c) for c in columns)
            for row in self.tables.get(table, []):
                if row is not ignore and tuple(row.get(c) for c in columns) == key:
                    raise UniqueViolation(f"{table}{columns}={key}")
