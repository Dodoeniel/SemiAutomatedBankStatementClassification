"""American Express PDF parser."""

from __future__ import annotations

import io
import re
from datetime import datetime

import pdfplumber

from ..models import Transaction
from .common import clean_text, compact_external_id, parse_amount


LINE_RE = re.compile(
    r"^(?P<sale>\d{2}\.\d{2})(?:\s+(?P<booking>\d{2}\.\d{2}))?\s+(?P<description>.+?)\s+(?P<amount>-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})$"
)


def _statement_date(text: str) -> datetime:
    match = re.search(r"\b(\d{2})\.(\d{2})\.(\d{2})\b", text)
    if match:
        day, month, year = match.groups()
        return datetime(2000 + int(year), int(month), int(day))
    return datetime.now()


def _date_from_day_month(value: str, statement_date: datetime) -> str:
    day, month = value.split(".")
    year = statement_date.year
    if int(month) > statement_date.month:
        year -= 1
    return datetime(year, int(month), int(day)).strftime("%Y-%m-%d")


def parse_amex_pdf(file_bytes: bytes) -> list[Transaction]:
    transactions = []
    all_text = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            all_text.append(page.extract_text() or "")

    text = "\n".join(all_text)
    statement_date = _statement_date(text)

    for line in text.splitlines():
        line = clean_text(line)
        match = LINE_RE.match(line)
        if not match:
            continue

        description = clean_text(match.group("description"))
        if not description or description.startswith("Saldo des laufenden Monats"):
            continue

        amount = parse_amount(match.group("amount"))
        description_folded = description.casefold()
        if "gutschrift" not in description_folded and "zahlung/überweisung erhalten" not in description_folded:
            amount = -abs(amount)

        booking_raw = match.group("booking") or match.group("sale")
        booking_date = _date_from_day_month(booking_raw, statement_date)
        value_date = _date_from_day_month(match.group("sale"), statement_date)

        transactions.append(
            Transaction(
                booking_date=booking_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                description=description,
                counterparty=description,
                source="amex",
                source_account="American Express",
                external_id=compact_external_id(booking_date, amount, description),
                raw_data={"line": line},
            )
        )

    return transactions
