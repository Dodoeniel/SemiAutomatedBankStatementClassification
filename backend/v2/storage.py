"""SQLite persistence for v2 transactions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .models import ClassificationSource, Transaction


def init_v2_db(db_path: str | Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_import_batches (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                filename TEXT,
                file_hash TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                transaction_count INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(source, file_hash)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_transactions (
                id INTEGER PRIMARY KEY,
                import_batch_id INTEGER,
                dedupe_key TEXT,
                budget_month TEXT,
                booking_date TEXT,
                value_date TEXT,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'EUR',
                description TEXT NOT NULL,
                counterparty TEXT,
                source TEXT,
                source_account TEXT,
                external_id TEXT,
                raw_data TEXT NOT NULL DEFAULT '{}',
                category_key TEXT,
                classification_source TEXT NOT NULL DEFAULT 'unknown',
                classification_rule_key TEXT,
                classification_confidence REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(import_batch_id) REFERENCES v2_import_batches(id)
            )
            """
        )
        _ensure_column(cur, "v2_transactions", "import_batch_id", "INTEGER")
        _ensure_column(cur, "v2_transactions", "dedupe_key", "TEXT")
        _ensure_column(cur, "v2_transactions", "budget_month", "TEXT")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_tx_booking_date ON v2_transactions (booking_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_tx_budget_month ON v2_transactions (budget_month)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_tx_category_key ON v2_transactions (category_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_tx_source ON v2_transactions (source)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_tx_dedupe_key ON v2_transactions (dedupe_key)")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(cur: sqlite3.Cursor, table_name: str, column_name: str, column_type: str) -> None:
    rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row[1] for row in rows}
    if column_name not in existing:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


class DuplicateImportError(Exception):
    def __init__(self, import_batch_id: int):
        super().__init__("Import file was already processed")
        self.import_batch_id = import_batch_id


class TransactionRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        init_v2_db(self.db_path)

    def create_import_batch(self, source: str, filename: str, file_hash: str, transaction_count: int) -> int:
        from datetime import datetime, timezone

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            existing = cur.execute(
                "SELECT id FROM v2_import_batches WHERE source = ? AND file_hash = ?",
                (source, file_hash),
            ).fetchone()
            if existing:
                raise DuplicateImportError(int(existing[0]))

            cur.execute(
                """
                INSERT INTO v2_import_batches (
                    source, filename, file_hash, imported_at, transaction_count,
                    inserted_count, duplicate_count
                ) VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    source,
                    filename,
                    file_hash,
                    datetime.now(timezone.utc).isoformat(),
                    transaction_count,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def update_import_batch_counts(self, import_batch_id: int, inserted_count: int, duplicate_count: int) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE v2_import_batches
                SET inserted_count = ?, duplicate_count = ?
                WHERE id = ?
                """,
                (inserted_count, duplicate_count, import_batch_id),
            )
            conn.commit()
        finally:
            conn.close()

    def insert(self, transaction: Transaction) -> Optional[int]:
        transaction.prepare_for_import()
        transaction.touch_for_insert()
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO v2_transactions (
                    import_batch_id, dedupe_key, budget_month,
                    booking_date, value_date, amount, currency, description, counterparty,
                    source, source_account, external_id, raw_data, category_key,
                    classification_source, classification_rule_key, classification_confidence,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.import_batch_id,
                    transaction.dedupe_key,
                    transaction.budget_month,
                    transaction.booking_date,
                    transaction.value_date,
                    str(transaction.amount),
                    transaction.currency,
                    transaction.description,
                    transaction.counterparty,
                    transaction.source,
                    transaction.source_account,
                    transaction.external_id,
                    json.dumps(transaction.raw_data, ensure_ascii=False, sort_keys=True),
                    transaction.category_key,
                    transaction.classification_source.value,
                    transaction.classification_rule_key,
                    transaction.classification_confidence,
                    transaction.created_at,
                    transaction.updated_at,
                ),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get(self, transaction_id: int) -> Transaction | None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM v2_transactions WHERE id = ?",
                (transaction_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_transaction(row)
        finally:
            conn.close()

    def list(
        self,
        *,
        year: str | None = None,
        month: str | None = None,
        budget_month: str | None = None,
        source: str | None = None,
        classified: str = "all",
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        where = []
        params: list[object] = []

        if budget_month:
            where.append("budget_month = ?")
            params.append(budget_month)
        else:
            if year:
                where.append("substr(budget_month, 1, 4) = ?")
                params.append(year)
            if month:
                where.append("substr(budget_month, 6, 2) = ?")
                params.append(month.zfill(2))

        if source:
            where.append("source = ?")
            params.append(source)

        if classified == "classified":
            where.append("category_key IS NOT NULL AND TRIM(category_key) <> ''")
        elif classified == "unclassified":
            where.append("(category_key IS NULL OR TRIM(category_key) = '')")

        where_sql = " WHERE " + " AND ".join(where) if where else ""
        params.extend([limit, offset])

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM v2_transactions
                {where_sql}
                ORDER BY budget_month DESC, booking_date DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
            return [self._row_to_api(row) for row in rows]
        finally:
            conn.close()

    def set_manual_category(self, transaction_id: int, category_key: str | None) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """
                UPDATE v2_transactions
                SET category_key = ?,
                    classification_source = ?,
                    classification_rule_key = NULL,
                    classification_confidence = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    category_key,
                    ClassificationSource.MANUAL.value if category_key else ClassificationSource.UNKNOWN.value,
                    1.0 if category_key else 0.0,
                    now,
                    transaction_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete(self, transaction_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM v2_transactions WHERE id = ?",
                (transaction_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_transaction(row: sqlite3.Row) -> Transaction:
        return Transaction(
            import_batch_id=row["import_batch_id"],
            dedupe_key=row["dedupe_key"],
            budget_month=row["budget_month"],
            booking_date=row["booking_date"],
            value_date=row["value_date"],
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            description=row["description"],
            counterparty=row["counterparty"],
            source=row["source"],
            source_account=row["source_account"],
            external_id=row["external_id"],
            raw_data=json.loads(row["raw_data"] or "{}"),
            category_key=row["category_key"],
            classification_source=ClassificationSource(row["classification_source"]),
            classification_rule_key=row["classification_rule_key"],
            classification_confidence=float(row["classification_confidence"] or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_api(row: sqlite3.Row) -> dict[str, object]:
        return {
            "id": row["id"],
            "import_batch_id": row["import_batch_id"],
            "budget_month": row["budget_month"],
            "booking_date": row["booking_date"],
            "value_date": row["value_date"],
            "amount": row["amount"],
            "currency": row["currency"],
            "description": row["description"],
            "counterparty": row["counterparty"],
            "source": row["source"],
            "source_account": row["source_account"],
            "category_key": row["category_key"],
            "classification_source": row["classification_source"],
            "classification_rule_key": row["classification_rule_key"],
            "classification_confidence": row["classification_confidence"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
