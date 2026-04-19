"""Analytics queries for v2 transactions."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .category_store import CategoryStore
from .models import CategoryType


def _money(value: object) -> float:
    return float(Decimal(str(value or "0")))


def _display_total(category_type: CategoryType, signed_total: float) -> float:
    if category_type == CategoryType.EXPENSE:
        return abs(signed_total)
    return signed_total


def _category_payload(category) -> dict[str, object]:
    return {
        "key": category.key,
        "type": category.type.value,
        "group": category.group,
        "name": category.name,
        "sort_order": category.sort_order,
    }


class AnalyticsService:
    def __init__(self, db_path: str | Path, category_store: CategoryStore):
        self.db_path = str(db_path)
        self.category_store = category_store

    def summary(self, *, year: Optional[str] = None, month: Optional[str] = None) -> dict[str, object]:
        rows = self._classified_rows(year=year, month=month)
        grouped: dict[str, dict[str, dict[str, dict[str, object]]]] = {
            "income": defaultdict(dict),
            "expense": defaultdict(dict),
        }

        for row in rows:
            category = self.category_store.get(row["category_key"])
            if not category:
                continue

            signed_amount = _money(row["amount"])
            type_key = category.type.value
            group = grouped[type_key][category.group]
            entry = group.setdefault(
                category.key,
                {
                    "category": _category_payload(category),
                    "signed_total": 0.0,
                    "display_total": 0.0,
                    "count": 0,
                    "entries": [],
                },
            )
            entry["signed_total"] += signed_amount
            entry["display_total"] = _display_total(category.type, entry["signed_total"])
            entry["count"] += 1
            entry["entries"].append(self._transaction_entry(row))

        return {
            "income": self._finalize_summary_groups(grouped["income"]),
            "expense": self._finalize_summary_groups(grouped["expense"]),
            "unclassified": self.unclassified(year=year, month=month),
        }

    def monthly(self) -> dict[str, object]:
        rows = self._classified_rows()
        months = sorted({row["budget_month"] for row in rows if row["budget_month"]})

        by_type: dict[str, dict[str, dict[str, float]]] = {
            "income": defaultdict(lambda: defaultdict(float)),
            "expense": defaultdict(lambda: defaultdict(float)),
        }
        category_meta = {}

        for row in rows:
            category = self.category_store.get(row["category_key"])
            budget_month = row["budget_month"]
            if not category or not budget_month:
                continue

            signed_amount = _money(row["amount"])
            by_type[category.type.value][category.key][budget_month] += signed_amount
            category_meta[category.key] = category

        def build_payload(type_key: str) -> dict[str, object]:
            keys = sorted(
                by_type[type_key].keys(),
                key=lambda key: category_meta[key].sort_order,
            )
            categories = [_category_payload(category_meta[key]) for key in keys]
            signed_data = {
                key: [by_type[type_key][key].get(month, 0.0) for month in months]
                for key in keys
            }
            display_data = {
                key: [
                    _display_total(category_meta[key].type, by_type[type_key][key].get(month, 0.0))
                    for month in months
                ]
                for key in keys
            }
            return {
                "months": months,
                "categories": categories,
                "signed_data": signed_data,
                "display_data": display_data,
            }

        income_totals = self._monthly_totals(by_type["income"], months, category_meta, display=False)
        expense_totals = self._monthly_totals(by_type["expense"], months, category_meta, display=True)
        net_totals = [income_totals[i] - expense_totals[i] for i in range(len(months))]

        return {
            "income": build_payload("income"),
            "expense": build_payload("expense"),
            "totals": {
                "months": months,
                "income": income_totals,
                "expense": expense_totals,
                "net": net_totals,
            },
        }

    def details(self, *, category_key: str, budget_month: str) -> dict[str, object]:
        category = self.category_store.require(category_key)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM v2_transactions
                WHERE category_key = ?
                  AND budget_month = ?
                ORDER BY value_date, booking_date, id
                """,
                (category_key, budget_month),
            ).fetchall()
        finally:
            conn.close()

        entries = [self._transaction_entry(row) for row in rows]
        signed_total = sum(_money(row["amount"]) for row in rows)
        return {
            "category": _category_payload(category),
            "budget_month": budget_month,
            "signed_total": signed_total,
            "display_total": _display_total(category.type, signed_total),
            "count": len(entries),
            "entries": entries,
        }

    def unclassified(self, *, year: Optional[str] = None, month: Optional[str] = None) -> dict[str, object]:
        where = ["(category_key IS NULL OR TRIM(category_key) = '')"]
        params: list[object] = []
        if year:
            where.append("substr(budget_month, 1, 4) = ?")
            params.append(year)
        if month:
            where.append("substr(budget_month, 6, 2) = ?")
            params.append(month.zfill(2))

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                f"""
                SELECT budget_month, source, COUNT(*) AS count
                FROM v2_transactions
                WHERE {" AND ".join(where)}
                GROUP BY budget_month, source
                ORDER BY budget_month DESC, source
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

        total = sum(int(row["count"]) for row in rows)
        return {
            "total": total,
            "buckets": [
                {
                    "budget_month": row["budget_month"],
                    "source": row["source"],
                    "count": int(row["count"]),
                }
                for row in rows
            ],
        }

    def _classified_rows(self, *, year: Optional[str] = None, month: Optional[str] = None) -> list[sqlite3.Row]:
        where = ["category_key IS NOT NULL", "TRIM(category_key) <> ''"]
        params: list[object] = []
        if year:
            where.append("substr(budget_month, 1, 4) = ?")
            params.append(year)
        if month:
            where.append("substr(budget_month, 6, 2) = ?")
            params.append(month.zfill(2))

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                f"""
                SELECT *
                FROM v2_transactions
                WHERE {" AND ".join(where)}
                ORDER BY budget_month DESC, value_date DESC, booking_date DESC, id DESC
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

    @staticmethod
    def _finalize_summary_groups(groups: dict[str, dict[str, dict[str, object]]]) -> list[dict[str, object]]:
        payload = []
        for group_name, categories in groups.items():
            items = sorted(
                categories.values(),
                key=lambda item: item["category"]["sort_order"],
            )
            group_signed_total = sum(item["signed_total"] for item in items)
            group_display_total = sum(item["display_total"] for item in items)
            payload.append(
                {
                    "group": group_name,
                    "signed_total": group_signed_total,
                    "display_total": group_display_total,
                    "count": sum(item["count"] for item in items),
                    "categories": items,
                }
            )
        return payload

    @staticmethod
    def _monthly_totals(type_map, months: list[str], category_meta, *, display: bool) -> list[float]:
        totals = []
        for month in months:
            total = 0.0
            for key, month_map in type_map.items():
                amount = month_map.get(month, 0.0)
                total += _display_total(category_meta[key].type, amount) if display else amount
            totals.append(total)
        return totals

    @staticmethod
    def _transaction_entry(row: sqlite3.Row) -> dict[str, object]:
        amount = _money(row["amount"])
        return {
            "id": row["id"],
            "budget_month": row["budget_month"],
            "booking_date": row["booking_date"],
            "value_date": row["value_date"],
            "amount": amount,
            "display_amount": abs(amount),
            "currency": row["currency"],
            "description": row["description"],
            "counterparty": row["counterparty"],
            "source": row["source"],
        }
