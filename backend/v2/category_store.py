"""Category loading and lookup helpers for v2 category records."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Category, CategoryType


class CategoryStore:
    def __init__(self, categories: list[Category]):
        self.categories = categories
        self._by_key = {category.key: category for category in categories}

    @classmethod
    def from_json_file(cls, path: str | Path) -> "CategoryStore":
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        categories = [
            Category(
                key=item["key"],
                type=CategoryType(item["type"]),
                group=item["group"],
                name=item["name"],
                sort_order=int(item.get("sort_order", 0)),
                active=bool(item.get("active", True)),
            )
            for item in payload.get("categories", [])
        ]
        return cls(categories)

    def get(self, key: str) -> Category | None:
        return self._by_key.get(key)

    def require(self, key: str) -> Category:
        category = self.get(key)
        if category is None:
            raise KeyError(f"Unknown category key: {key}")
        return category

    def active_keys(self) -> set[str]:
        return {category.key for category in self.categories if category.active}

    def as_api_payload(self) -> dict[str, list[dict[str, object]]]:
        return {
            "categories": [
                {
                    "key": category.key,
                    "type": category.type.value,
                    "group": category.group,
                    "name": category.name,
                    "sort_order": category.sort_order,
                    "active": category.active,
                }
                for category in self.categories
            ]
        }

