"""Revolut CSV parser."""

from __future__ import annotations

import csv
import io

from ..models import Transaction
from .common import clean_text, compact_external_id, parse_amount, parse_date


def parse_revolut_csv(file_bytes: bytes) -> list[Transaction]:
    text = file_bytes.decode("utf-8-sig", errors="ignore")
    sample = text[:8192]
    delimiter = "\t" if sample.count("\t") >= max(sample.count(";"), sample.count(",")) else (";" if sample.count(";") > sample.count(",") else ",")
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    required = {"Datum des Beginns", "Datum des Abschlusses", "Beschreibung", "Betrag", "Währung"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Revolut CSV: erwartete Spalten fehlen: {', '.join(sorted(missing))}")

    transactions = []
    for row in reader:
        booking_date = parse_date(row.get("Datum des Beginns"), ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"))
        value_date = parse_date(row.get("Datum des Abschlusses"), ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"))
        description = clean_text(row.get("Beschreibung"))
        amount = parse_amount(row.get("Betrag"))

        if not booking_date and not description:
            continue

        transactions.append(
            Transaction(
                booking_date=booking_date or value_date,
                value_date=value_date,
                amount=amount,
                currency=clean_text(row.get("Währung")) or "EUR",
                description=description,
                counterparty=description or None,
                source="revolut",
                source_account=clean_text(row.get("Produkt")) or "Revolut",
                external_id=compact_external_id(booking_date, value_date, amount, description),
                raw_data={str(k): clean_text(v) for k, v in row.items()},
            )
        )

    return transactions

