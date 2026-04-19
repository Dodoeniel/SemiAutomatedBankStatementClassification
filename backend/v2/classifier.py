"""Rule-based transaction classification."""

from __future__ import annotations

import re
from typing import Any

from .models import ClassificationResult, ClassificationSource, MatchType, Transaction
from .rule_store import RuleStore


def _normalize(value: Any) -> str:
    return str(value or "").strip().casefold()


class RuleBasedClassifier:
    def __init__(self, rule_store: RuleStore):
        self.rule_store = rule_store

    def classify(self, transaction: Transaction) -> ClassificationResult:
        for rule in self.rule_store.rules:
            if not rule.active:
                continue
            if rule.source_filter and rule.source_filter != transaction.source:
                continue
            if self._matches_rule(transaction, rule):
                return ClassificationResult(
                    category_key=rule.category_key,
                    source=ClassificationSource.RULE,
                    rule_key=rule.key,
                    confidence=1.0,
                )

        return ClassificationResult(
            category_key=None,
            source=ClassificationSource.UNKNOWN,
            confidence=0.0,
        )

    def _matches_rule(self, transaction: Transaction, rule) -> bool:
        pattern = _normalize(rule.pattern)
        if not pattern:
            return False

        for field_name in rule.match_fields:
            field_value = _normalize(getattr(transaction, field_name, ""))
            if not field_value:
                continue

            if rule.match_type == MatchType.CONTAINS and pattern in field_value:
                return True
            if rule.match_type == MatchType.EXACT and pattern == field_value:
                return True
            if rule.match_type == MatchType.STARTS_WITH and field_value.startswith(pattern):
                return True
            if rule.match_type == MatchType.REGEX:
                try:
                    if re.search(rule.pattern, field_value, flags=re.IGNORECASE):
                        return True
                except re.error:
                    return False

        return False

