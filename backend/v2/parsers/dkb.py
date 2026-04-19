"""DKB Giro CSV parser."""

from __future__ import annotations

import csv
import io

from ..models import Transaction
from .common import clean_text, compact_external_id, parse_amount, parse_date


def parse_dkb_giro_csv(file_bytes: bytes) -> list[Transaction]:
    text = file_bytes.decode("utf-8-sig", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]

    header_idx = None
    for idx, line in enumerate(lines):
        if "Buchungsdatum" in line and "Betrag" in line and "Verwendungszweck" in line:
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("DKB CSV: Tabellenkopf nicht gefunden.")

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])), delimiter=";")
    transactions = []
    for row in reader:
        booking_date = parse_date(row.get("Buchungsdatum"), ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"))
        value_date = parse_date(row.get("Wertstellung"), ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"))
        amount = parse_amount(row.get("Betrag (€)"))
        payer = clean_text(row.get("Zahlungspflichtige*r"))
        payee = clean_text(row.get("Zahlungsempfänger*in"))
        transaction_type = clean_text(row.get("Umsatztyp")).casefold()
        if transaction_type == "eingang":
            counterparty = payer or payee
        elif transaction_type == "ausgang":
            counterparty = payee or payer
        elif amount > 0:
            counterparty = payer or payee
        elif amount < 0:
            counterparty = payee or payer
        else:
            counterparty = payee or payer
        description = clean_text(row.get("Verwendungszweck") or counterparty)

        if not booking_date and not description:
            continue

        transactions.append(
            Transaction(
                booking_date=booking_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                description=description,
                counterparty=counterparty or None,
                source="dkb_giro",
                source_account="DKB Giro",
                external_id=compact_external_id(
                    row.get("Kundenreferenz"),
                    row.get("Mandatsreferenz"),
                    booking_date,
                    amount,
                    description,
                ),
                raw_data={str(k): clean_text(v) for k, v in row.items()},
            )
        )

    return transactions
