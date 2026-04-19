"""Classification rule loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

from .category_store import CategoryStore
from .models import ClassificationRule, MatchType


class RuleStore:
    def __init__(self, rules: list[ClassificationRule]):
        self.rules = sorted(
            rules,
            key=lambda rule: (-rule.priority, rule.key),
        )

    @classmethod
    def from_json_file(
        cls,
        path: str | Path,
        category_store: CategoryStore | None = None,
    ) -> "RuleStore":
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        active_category_keys = category_store.active_keys() if category_store else None
        rules = []
        for item in payload.get("rules", []):
            category_key = item["category_key"]
            if active_category_keys is not None and category_key not in active_category_keys:
                raise ValueError(
                    f"Rule {item.get('key', '<unknown>')} references unknown category {category_key}"
                )

            rules.append(
                ClassificationRule(
                    key=item["key"],
                    pattern=item["pattern"],
                    category_key=category_key,
                    match_fields=tuple(item.get("match_fields", ["description", "counterparty"])),
                    match_type=MatchType(item.get("match_type", MatchType.CONTAINS.value)),
                    source_filter=item.get("source_filter"),
                    priority=int(item.get("priority", 100)),
                    active=bool(item.get("active", True)),
                )
            )
        return cls(rules)

    def as_api_payload(self) -> dict[str, list[dict[str, object]]]:
        return {
            "rules": [
                {
                    "key": rule.key,
                    "pattern": rule.pattern,
                    "match_type": rule.match_type.value,
                    "match_fields": list(rule.match_fields),
                    "category_key": rule.category_key,
                    "source_filter": rule.source_filter,
                    "priority": rule.priority,
                    "active": rule.active,
                }
                for rule in self.rules
            ]
        }

