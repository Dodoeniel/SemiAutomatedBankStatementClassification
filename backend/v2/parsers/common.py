"""Shared parser helpers for v2 statement importers."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def parse_date(value: object, formats: tuple[str, ...]) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_amount(value: object) -> Decimal:
    text = clean_text(value)
    if not text:
        return Decimal("0")

    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text or text == "-":
        return Decimal("0")

    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "." in text and re.match(r"^-?\d{1,3}(?:\.\d{3})+$", text):
        text = text.replace(".", "")

    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def compact_external_id(*parts: object) -> str:
    text = "|".join(clean_text(part) for part in parts if clean_text(part))
    return text[:300]

