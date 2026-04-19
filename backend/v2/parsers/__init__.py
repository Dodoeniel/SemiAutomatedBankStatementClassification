"""Parser registry for v2 statement sources."""

from __future__ import annotations

from ..models import Transaction
from .amex import parse_amex_pdf
from .deutsche_bank import parse_deutsche_bank_credit_pdf
from .dkb import parse_dkb_giro_csv
from .revolut import parse_revolut_csv


PARSERS = {
    "amex": parse_amex_pdf,
    "deutsche_bank_miles_more": parse_deutsche_bank_credit_pdf,
    "dkb_giro": parse_dkb_giro_csv,
    "revolut": parse_revolut_csv,
}


def parse_statement(source: str, file_bytes: bytes) -> list[Transaction]:
    parser = PARSERS.get(source)
    if parser is None:
        raise ValueError(f"Unknown v2 statement source: {source}")
    return parser(file_bytes)


def supported_sources() -> list[str]:
    return sorted(PARSERS.keys())

