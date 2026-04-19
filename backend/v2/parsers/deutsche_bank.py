"""Deutsche Bank Miles & More credit card PDF parser."""

from __future__ import annotations

import io
import re

import pdfplumber

from ..models import Transaction
from .common import clean_text, compact_external_id, parse_amount, parse_date


LINE_RE = re.compile(
    r"^(?P<receipt>\d{2}\.\d{2}\.\d{4})\s+(?P<booking>\d{2}\.\d{2}\.\d{4})\s+(?P<description>.+?)\s+(?P<amount>-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})$"
)


def parse_deutsche_bank_credit_pdf(file_bytes: bytes) -> list[Transaction]:
    transactions = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    for line in text.splitlines():
        line = clean_text(line)
        match = LINE_RE.match(line)
        if not match:
            continue

        description = clean_text(match.group("description"))
        if description.casefold().startswith("saldo"):
            continue

        booking_date = parse_date(match.group("booking"), ("%d.%m.%Y",))
        value_date = parse_date(match.group("receipt"), ("%d.%m.%Y",))
        amount = parse_amount(match.group("amount"))

        transactions.append(
            Transaction(
                booking_date=booking_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                description=description,
                counterparty=description,
                source="deutsche_bank_miles_more",
                source_account="Deutsche Bank Miles & More Kreditkarte",
                external_id=compact_external_id(booking_date, amount, description),
                raw_data={"line": line},
            )
        )

    return transactions

