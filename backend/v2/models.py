"""Domain models for the v2 transaction and classification flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import re
from typing import Any, Optional


class CategoryType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class ClassificationSource(str, Enum):
    UNKNOWN = "unknown"
    RULE = "rule"
    MANUAL = "manual"
    IMPORTED = "imported"


class MatchType(str, Enum):
    CONTAINS = "contains"
    EXACT = "exact"
    STARTS_WITH = "starts_with"
    REGEX = "regex"


@dataclass(frozen=True)
class Category:
    key: str
    type: CategoryType
    group: str
    name: str
    sort_order: int = 0
    active: bool = True


@dataclass(frozen=True)
class ClassificationRule:
    key: str
    pattern: str
    category_key: str
    match_fields: tuple[str, ...] = ("description", "counterparty")
    match_type: MatchType = MatchType.CONTAINS
    source_filter: Optional[str] = None
    priority: int = 100
    active: bool = True


@dataclass(frozen=True)
class ClassificationResult:
    category_key: Optional[str]
    source: ClassificationSource
    rule_key: Optional[str] = None
    confidence: float = 0.0


@dataclass
class Transaction:
    booking_date: Optional[str]
    amount: Decimal
    currency: str
    description: str
    counterparty: Optional[str] = None
    value_date: Optional[str] = None
    source: Optional[str] = None
    source_account: Optional[str] = None
    external_id: Optional[str] = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    budget_month: Optional[str] = None
    dedupe_key: Optional[str] = None
    import_batch_id: Optional[int] = None
    category_key: Optional[str] = None
    classification_source: ClassificationSource = ClassificationSource.UNKNOWN
    classification_rule_key: Optional[str] = None
    classification_confidence: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def apply_classification(self, result: ClassificationResult) -> None:
        self.category_key = result.category_key
        self.classification_source = result.source
        self.classification_rule_key = result.rule_key
        self.classification_confidence = result.confidence

    def touch_for_insert(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = self.created_at or now
        self.updated_at = self.updated_at or now

    def prepare_for_import(self) -> None:
        self.budget_month = self.budget_month or derive_budget_month(self)
        self.dedupe_key = self.dedupe_key or build_dedupe_key(self)


def normalize_dedupe_text(value: object) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def derive_budget_month(transaction: Transaction) -> Optional[str]:
    date_value = transaction.value_date or transaction.booking_date
    if isinstance(date_value, str) and re.match(r"^\d{4}-\d{2}", date_value):
        return date_value[:7]
    return None


def build_dedupe_key(transaction: Transaction) -> str:
    external_or_description = transaction.external_id or normalize_dedupe_text(transaction.description)
    parts = [
        normalize_dedupe_text(transaction.source),
        transaction.booking_date or "",
        transaction.value_date or "",
        str(transaction.amount),
        transaction.currency,
        normalize_dedupe_text(transaction.counterparty),
        normalize_dedupe_text(external_or_description),
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
