"""
Bank statement backend.
Stores NULL (not 'NaN') for missing categories, and computes consolidated `final_category` at insert.
"""
import re
import pdfplumber
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import json
import os
import sqlite3
from typing import Optional
from datetime import datetime

# --- Robust date to YYYY-MM helper ---
def to_year_month(d) -> Optional[str]:
    """Return 'YYYY-MM' for diverse date inputs or None if unparseable, without pandas warnings."""
    if not d:
        return None
    s = str(d).strip()

    # 1) Schneller Pfad: ISO 'YYYY-MM' oder 'YYYY-MM-DD'
    #    Kein dayfirst-Problem, also direkt parsen mit strptime
    m = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$", s)
    if m:
        try:
            year = int(m.group(1)); month = int(m.group(2))
            # valid month 1..12
            if 1 <= month <= 12:
                return f"{year:04d}-{month:02d}"
        except Exception:
            pass

    # 2) Häufige europäische Formate explizit
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime('%Y-%m')
        except Exception:
            pass

    # 3) Fallback: pandas parser (ohne infer_datetime_format), mit dayfirst=True
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%Y-%m')
    except Exception:
        pass

    return None

APP_DIR = os.path.dirname(__file__)
# Allow overriding storage paths via environment variables (for Docker volumes)
DATA_DIR = os.getenv("DATA_DIR", APP_DIR)
# categories.json ist Teil des Images/Repos → standardmäßig aus APP_DIR laden (nicht aus DATA_DIR),
# aber weiterhin über CATEGORIES_PATH überschreibbar.
CATEGORIES_PATH = os.getenv("CATEGORIES_PATH", os.path.join(APP_DIR, "categories.json"))
KEYWORDS_PATH = os.getenv("KEYWORDS_PATH", os.path.join(DATA_DIR, "keywords.json"))
SUMMARY_PATH = os.getenv("SUMMARY_PATH", os.path.join(DATA_DIR, "summary_spendings.json"))
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "transactions.db"))

# --- Simple DB helper (sqlite) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            buchungsdatum TEXT,
            zahlungsempfaenger TEXT,
            verwendungszweck TEXT,
            betrag TEXT,
            category_empfaenger TEXT,
            category_pflichtig TEXT,
            category_verwendungszweck TEXT,
            final_category INTEGER,
            processed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Load categories and keywords ---
with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
    categories = json.load(f)

if os.path.exists(KEYWORDS_PATH):
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        keywords = json.load(f)
else:
    keywords = {}

# --- Helpers ---
def classify_statement(description: Optional[str]) -> Optional[str]:
    """
    Classify a statement description to a category id, or return None if no match.
    Matches keywords case-insensitively after trimming.
    """
    if not isinstance(description, str):
        return None
    hay = description.strip().casefold()
    if not hay:
        return None
    for kw, meta in keywords.items():
        if str(kw).strip().casefold() in hay:
            return meta.get("id")
    return None

def read_dkb_statement_csv_bytes(file_bytes) -> pd.DataFrame:
    df = pd.read_csv(pd.io.common.BytesIO(file_bytes), skiprows=4, header=None, delimiter=';')
    df.columns = df.iloc[0]
    df = df[1:]
    drop_cols = ['Mandatsreferenz', 'Kundenreferenz', 'Gläubiger-ID', 'IBAN', 'Umsatztyp', 'Status']
    for c in drop_cols:
        if c in df.columns:
            df = df.drop(columns=[c])
    if 'Verwendungszweck' in df and 'Zahlungsempfänger*in' in df:
        df['Verwendungszweck'] = df['Verwendungszweck'].fillna(df['Zahlungsempfänger*in'])

    # --- Betrag-Spalte robust finden und normalisieren ---
    def _normalize_dkb_amount(val):
        if pd.isna(val):
            return ""
        s = str(val).strip().replace("\u00a0", "")  # NBSP entfernen
        # Währungssymbole/Leerzeichen entfernen
        s = re.sub(r"[€\s]", "", s)
        # Wenn Komma vorhanden: deutsches Format -> Punkte (Tausender) entfernen, Komma zu Punkt
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
            return s
        # Kein Komma, aber Punkte: prüfen ob Tausenderpunkte (Gruppen à 3)
        if "." in s:
            if re.match(r"^-?\d{1,3}(?:\.\d{3})+(?:\.\d+)?$", s):
                s = s.replace(".", "")
                return s
            # Sonst Punkt als Dezimal lassen
            return s
        # Nur Ziffern/Minus
        return s

    # Betrag-Spalte robust finden und normalisieren
    amount_col = None
    for c in df.columns:
        if isinstance(c, str) and c.strip().startswith("Betrag"):
            amount_col = c
            break
    if amount_col is None:
        # Fallbacks versuchen
        for c in df.columns:
            if str(c).lower().startswith("betrag"):
                amount_col = c
                break
    if amount_col is not None:
        df[amount_col] = df[amount_col].apply(_normalize_dkb_amount)
        # Für nachfolgende Verarbeitung sicherstellen, dass 'Betrag (€)' existiert
        if amount_col != 'Betrag (€)':
            df['Betrag (€)'] = df[amount_col]
        # Final sicherstellen, dass 'Betrag (€)' sauber formatiert ist ('.' Dezimal, keine Tausender)
        df['Betrag (€)'] = df['Betrag (€)'].apply(_normalize_dkb_amount)

    # ➜ Datum vereinheitlichen (DD.MM.YY / DD.MM.YYYY / ISO → YYYY-MM-DD) ohne Inferenz-Warnungen
    def _parse_dkb_date(val):
        if pd.isna(val):
            return None
        s = str(val).strip().replace('\u00a0', ' ')
        # Versuche feste Formate zuerst, um Pandas-Warnungen zu vermeiden
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
            except Exception:
                pass
        # Fallback: pandas, tolerant
        try:
            dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
            if pd.notna(dt):
                return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None

    if 'Buchungsdatum' in df.columns:
        df['Buchungsdatum'] = df['Buchungsdatum'].apply(_parse_dkb_date)

    return df

# --- DKB Kreditkartenumsätze (separate CSV layout) ---
def read_dkb_credit_csv_bytes(file_bytes) -> pd.DataFrame:
    """
    Parser für DKB Kreditkartenumsätze (CSV-Export mit Kopfzeilen wie
    "Karte ...", "Saldo vom ..." und dann einer Tabelle mit:
    Belegdatum | Wertstellung | Status | Beschreibung | Umsatztyp | Betrag (€) | Fremdwährungsbetrag

    Gibt zurück im gemeinsamen Schema: Buchungsdatum, Zahlungsempfänger*in, Verwendungszweck, Betrag (€).
    """
    # 1) Rohtext laden (UTF-8 mit BOM tolerieren)
    try:
        text = file_bytes.decode('utf-8-sig', errors='ignore')
    except Exception:
        text = str(file_bytes)

    # 2) Delimiter-Heuristik
    if text.count('\t') >= max(text.count(';'), text.count(',')):
        delim = '\t'
    elif text.count(';') >= text.count(','):
        delim = ';'
    else:
        delim = ','

    # 3) Headerzeile suchen (erste Zeile, die die zentralen Spalten enthält)
    lines = [ln for ln in text.splitlines() if ln.strip() != '']
    header_idx = None
    must_haves = ['Belegdatum', 'Status', 'Beschreibung', 'Betrag']
    for i, ln in enumerate(lines):
        # grobe Prüfung, unabhängig vom konkreten Trennzeichen
        if all(m in ln for m in must_haves):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("DKB Kreditkarte: Tabellenkopf nicht gefunden (erwarte Spalten wie 'Belegdatum', 'Beschreibung', 'Betrag').")

    table_text = "\n".join(lines[header_idx:])

    # 4) CSV in DataFrame einlesen
    df = pd.read_csv(io.StringIO(table_text), sep=delim, engine='python')

    # 5) Spaltennamen säubern
    df.columns = [str(c).strip() for c in df.columns]

    # 6) Erwartete Spalten prüfen
    needed = ['Belegdatum', 'Beschreibung']
    if not all(col in df.columns for col in needed):
        raise ValueError("DKB Kreditkarte: erwartete Spalten fehlen (mind. 'Belegdatum', 'Beschreibung').")

    # 7) Betrag säubern/normalisieren
    amount_col = None
    for c in df.columns:
        if str(c).strip().startswith('Betrag'):
            amount_col = c
            break
    if amount_col is None:
        # Fallback auf exakt "Betrag (€)"
        if 'Betrag (€)' in df.columns:
            amount_col = 'Betrag (€)'
        else:
            raise ValueError("DKB Kreditkarte: Betrag-Spalte nicht gefunden.")

    df[amount_col] = df[amount_col].apply(parse_betrag)

    # 8) Datum parsen (Belegdatum bevorzugt)
    def _parse_cc_date(s):
        if pd.isna(s):
            return None
        s = str(s).strip()
        # typische Formen: 03.09.25 / 03.09.2025 / 2025-09-03
        for fmt in ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
            except Exception:
                pass
        try:
            dt = pd.to_datetime(s, errors='coerce', dayfirst=True)
            if pd.notna(dt):
                return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None

    buchungsdatum = df['Belegdatum'].apply(_parse_cc_date)

    # 9) Beschreibung → Zweck & (mangels Feld) auch Empfänger
    beschreibung = df['Beschreibung'].astype(str).fillna('').str.strip()

    # 10) Output in einheitliches Schema bringen
    out = pd.DataFrame({
        'Buchungsdatum': buchungsdatum,
        'Zahlungsempfänger*in': beschreibung,  # kein separates Empfängerfeld im Export
        'Verwendungszweck': beschreibung,
        'Betrag (€)': df[amount_col].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) else ""),
    })

    # 11) Leere Zeilen filtern
    out = out[~(out['Buchungsdatum'].isna() & (out['Verwendungszweck'].str.strip() == ''))]
    out.reset_index(drop=True, inplace=True)
    return out

def parse_amex_date(date_str):
    # date_str könnte "18.12" oder "18.12.24" sein
    parts = date_str.split('.')
    day = int(parts[0])
    month = int(parts[1])
    year = datetime.now().year
    if len(parts) == 3:
        year = int('20' + parts[2]) if len(parts[2]) == 2 else int(parts[2])
    return datetime(year, month, day).strftime('%Y-%m-%d')

def read_amex_statement_pdf(file_bytes) -> pd.DataFrame:
    transactions = []
    date_pattern = re.compile(r'\d{2}\.\d{2}')  # DD.MM Format

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split("\n")
                for line in lines:
                    parts = line.split()
                    if len(parts) > 3 and date_pattern.match(parts[0]):
                        try:
                            # Prüfe, ob die Zeile mit zwei Datumswerten beginnt
                            if len(parts) > 4 and date_pattern.match(parts[0]) and date_pattern.match(parts[1]):
                                date = parse_amex_date(parts[0])
                                description = " ".join(parts[2:-1])
                            else:
                                date = parse_amex_date(parts[0])
                                description = " ".join(parts[1:-1])
                            # AMEX Besonderheit: positive Werte sind Belastungen (gehen vom Konto ab).
                            # In unserer Konvention sollen Ausgaben negativ sein -> Vorzeichen umdrehen.
                            amount_str = clean_amount_string(parts[-1])
                            if amount_str not in ("", "-", None):
                                try:
                                    amount = float(amount_str)
                                    # AMEX Besonderheit: positive Werte sind Belastungen (gehen vom Konto ab).
                                    # In unserer Konvention sollen Ausgaben negativ sein -> Vorzeichen umdrehen.
                                    amount = -amount
                                    transactions.append([date, description, amount])
                                except ValueError as e:
                                    print(f"ERROR processing line: {line} -> {e}")
                                    continue
                        except Exception as e:
                            print(f"ERROR processing line: {line} -> {e}")
                            continue

    df = pd.DataFrame(transactions, columns=["Datum", "Verwendungszweck", "Betrag"])

    return df

import csv

def read_revolut_statement_csv(file_bytes) -> pd.DataFrame:
    """
    Schlanker Parser für den deutschen Revolut-Export.
    Erwartete Header:
      Art | Produkt | Datum des Beginns | Datum des Abschlusses | Beschreibung | Betrag | Gebühr | Währung | Status [| Kontostand]
    ("Kontostand" ist optional.)

    Mapping → einheitliches Schema (wie DKB/AMEX):
      - Buchungsdatum        := Datum des Beginns, sonst Datum des Abschlusses (YYYY-MM-DD)
      - Verwendungszweck     := Beschreibung
      - Zahlungsempfänger*in := Beschreibung (kein separates Feld vorhanden)
      - Betrag (€)           := normalisiert (Dezimalpunkt, keine Tausender)
    """
    # Delimiter-Heuristik: Tab vor Semikolon vor Komma
    try:
        head = file_bytes[:8192].decode('utf-8-sig', errors='ignore')
    except Exception:
        head = str(file_bytes[:8192])
    if head.count('\t') >= max(head.count(';'), head.count(',')):
        delim = '\t'
    elif head.count(';') >= head.count(','):
        delim = ';'
    else:
        delim = ','

    # CSV einlesen
    df = pd.read_csv(io.BytesIO(file_bytes), sep=delim, engine='python')

    # Header säubern
    def clean_col(c):
        return str(c).lstrip('\ufeff').strip()
    df.columns = [clean_col(c) for c in df.columns]

    # Pflichtspalten (Kontostand optional)
    required = ['Art', 'Produkt', 'Datum des Beginns', 'Datum des Abschlusses', 'Beschreibung', 'Betrag', 'Gebühr', 'Währung', 'Status']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Revolut CSV: erwartete Spalten fehlen: {', '.join(missing)}")

    # Datum: bevorzugt Beginn, sonst Abschluss (beide können DateTime sein)
    start_dt = pd.to_datetime(df['Datum des Beginns'], errors='coerce')
    done_dt  = pd.to_datetime(df['Datum des Abschlusses'], errors='coerce')
    used_dt  = start_dt.where(start_dt.notna(), done_dt)
    buchungsdatum = used_dt.dt.strftime('%Y-%m-%d').astype(object).where(used_dt.notna(), None)

    # Beschreibung → Zweck und Empfänger
    beschreibung = df['Beschreibung'].astype(str).fillna("").str.strip()

    # Betrag normalisieren
    betrag = df['Betrag'].apply(parse_betrag)
    betrag_str = betrag.apply(lambda x: f"{float(x):.2f}" if pd.notna(x) else "")

    out = pd.DataFrame({
        'Buchungsdatum': buchungsdatum,
        'Zahlungsempfänger*in': beschreibung,
        'Verwendungszweck': beschreibung,
        'Betrag (€)': betrag_str,
    })

    # Zeilen ohne Datum UND ohne Zweck aussieben
    out = out[~(out['Buchungsdatum'].isna() & (out['Verwendungszweck'].str.strip() == ''))]
    out.reset_index(drop=True, inplace=True)
    return out


def insert_transactions_from_df(df: pd.DataFrame):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    def _nn(v):
        """Normalize value: return None for NaN/NaT/empty strings, else str(v)."""
        if v is None:
            return None
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        s = str(v).strip()
        if s == '' or s.lower() in ('nan', 'nat', 'none'):
            return None
        return s

    for _, row in df.iterrows():
        buchungsdatum = (
            row.get('Buchungsdatum')
            or row.get('Datum')
            or row.get('Started Date')
            or row.get('Datum des Beginns')
            or row.get('Datum des Abschlusses')
            or ''
        )
        zahlungsempfaenger = row.get('Zahlungsempfänger*in') or row.get('Merchant') or ''
        verwendungszweck = row.get('Verwendungszweck') or row.get('Description') or ''
        betrag_value = row.get('Betrag (€)') or row.get('Betrag') or row.get('Amount') or ''

        # Klassifizieren (None statt 'NaN' wenn kein Match)
        cat_empf = classify_statement(str(zahlungsempfaenger))
        cat_pfl  = classify_statement(str(row.get('Zahlungspflichtige*r', '')) if 'Zahlungspflichtige*r' in row else None)
        cat_verw = classify_statement(str(verwendungszweck))

        # Konsolidiert
        final_cat = cat_verw or cat_empf or cat_pfl

        cur.execute("""
            INSERT INTO transactions (
                buchungsdatum, zahlungsempfaenger, verwendungszweck, betrag,
                category_empfaenger, category_pflichtig, category_verwendungszweck, final_category, processed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            _nn(buchungsdatum),
            _nn(zahlungsempfaenger),
            _nn(verwendungszweck),
            _nn(betrag_value),
            _nn(cat_empf),
            _nn(cat_pfl),
            _nn(cat_verw),
            int(final_cat) if (
                isinstance(final_cat, (int, float)) or
                (isinstance(final_cat, str) and final_cat.isdigit()) or
                (isinstance(final_cat, str) and final_cat and final_cat.replace('-', '').isdigit())
            ) else None
        ))
    conn.commit()
    conn.close()

def parse_betrag(betrag_str):
    try:
        # Direkt Zahl durchreichen
        if isinstance(betrag_str, (float, int)):
            return float(betrag_str)
        if betrag_str is None:
            return 0.0
        s = str(betrag_str).strip()
        if s == "":
            return 0.0
        # Alles außer Ziffern, Trennzeichen und Minus entfernen
        s = re.sub(r"[^0-9.,\-]", "", s)
        # Regeln:
        # 1) Enthält Komma -> Komma ist Dezimaltrennzeichen, Punkt sind Tausender
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
            return float(s)
        # 2) Kein Komma, aber Punkte vorhanden
        if "." in s:
            # Wenn Muster wie 1.234 oder 1.234.567 (Gruppen à 3) -> Punkte sind Tausender -> entfernen
            if re.match(r"^-?\d{1,3}(?:\.\d{3})+(?:\.\d+)?$", s):
                # Wenn ganz am Ende nochmal .xx vorkommt, könnte das eigentlich Dezimal sein. 
                # DKB nutzt aber Komma für Dezimal, daher Punkte als Tausender entfernen.
                s = s.replace(".", "")
                return float(s)
            # Sonst: Punkt als Dezimaltrennzeichen akzeptieren
            return float(s)
        # 3) Nur Ziffern/Minus -> direkt casten
        return float(s)
    except Exception as e:
        print(f"ERROR converting betrag '{betrag_str}': {e}")
        return 0.0

def clean_amount_string(amount_str: str) -> str:
    # Entfernt alles außer Ziffern, Minus, Punkt und Komma
    amount_str = re.sub(r"[^0-9,.\-]", "", amount_str)
    # Wenn Komma vorkommt → Punkt als Tausendertrennung entfernen, Komma durch Punkt ersetzen
    if "," in amount_str:
        amount_str = amount_str.replace(".", "").replace(",", ".")
    else:
        # Falls kein Komma, Punkt als Dezimaltrennzeichen lassen
        pass
    return amount_str

# --- App ---
app = Flask(__name__)
CORS(app)

@app.route("/upload-statement", methods=["POST"])
def upload_statement():
    if 'file' not in request.files:
        return jsonify({"detail": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"detail": "No selected file"}), 400
    bank = request.form.get('bank', '').lower()
    content = file.read()
    try:
        if bank == "dkb":
            df = read_dkb_statement_csv_bytes(content)
        elif bank == "revolut":
            df = read_revolut_statement_csv(content)
        elif bank == "amex":
            df = read_amex_statement_pdf(content)
        else:
            return jsonify({"detail": "Unknown bank type"}), 400

        # Jetzt df ins DB speichern
        insert_transactions_from_df(df)

        return jsonify({"inserted": len(df)})
    except Exception as e:
        return jsonify({"detail": f"Parsing failed: {e}"}), 400


# --- DKB Kreditkartenumsätze dedicated upload endpoint ---
@app.route("/upload-statement-dkb-credit", methods=["POST"])
def upload_statement_dkb_credit():
    if 'file' not in request.files:
        return jsonify({"detail": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"detail": "No selected file"}), 400
    content = file.read()
    try:
        df = read_dkb_credit_csv_bytes(content)
        insert_transactions_from_df(df)
        return jsonify({"inserted": len(df)})
    except Exception as e:
        return jsonify({"detail": f"Parsing failed: {e}"}), 400


# --- General transactions endpoint with optional filters ---
@app.route("/transactions", methods=["GET"])
def get_transactions():
    """Return transactions with optional filters:
    - year: 'YYYY'
    - month: 'MM'
    - classified: 'all' | 'classified' | 'unclassified'
    """
    try:
        year = (request.args.get('year') or '').strip()
        month = (request.args.get('month') or '').strip()
        classified = (request.args.get('classified') or 'all').strip().lower()

        where = []
        params = []

        # Date filter: prefer ISO 'YYYY-MM' prefix, fallback keeps flexible matching
        if year:
            where.append("substr(buchungsdatum,1,4) = ?")
            params.append(year)
        if month:
            # month should be two digits
            if len(month) == 1:
                month = month.zfill(2)
            where.append("substr(buchungsdatum,6,2) = ?")
            params.append(month)

        if classified in ('classified', 'unclassified'):
            classified_sql = (
                "( final_category IS NOT NULL "
                "  OR (category_verwendungszweck IS NOT NULL AND TRIM(category_verwendungszweck) <> '' AND LOWER(category_verwendungszweck) <> 'nan') "
                "  OR (category_empfaenger IS NOT NULL AND TRIM(category_empfaenger) <> '' AND LOWER(category_empfaenger) <> 'nan') "
                "  OR (category_pflichtig IS NOT NULL AND TRIM(category_pflichtig) <> '' AND LOWER(category_pflichtig) <> 'nan') )"
            )
            if classified == 'classified':
                where.append(classified_sql)
            else:
                where.append(f"NOT {classified_sql}")

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(f"""
            SELECT 
                id,
                buchungsdatum,
                zahlungsempfaenger,
                verwendungszweck,
                betrag,
                category_empfaenger,
                category_pflichtig,
                category_verwendungszweck,
                final_category,
                processed,
                COALESCE(category_verwendungszweck, category_empfaenger, category_pflichtig) AS cat_id
            FROM transactions
            {where_sql}
            ORDER BY buchungsdatum DESC, id DESC
        """, params)
        rows = cur.fetchall()
        conn.close()

        txs = []
        for r in rows:
            txs.append({
                "id": r[0],
                "buchungsdatum": r[1],
                "zahlungsempfaenger": r[2],
                "verwendungszweck": r[3],
                "betrag": r[4],
                "category_empfaenger": r[5],
                "category_pflichtig": r[6],
                "category_verwendungszweck": r[7],
                "final_category": r[8],
                "processed": r[9],
                "cat_id": r[10],
            })

        return jsonify({"transactions": txs})
    except Exception as e:
        return jsonify({"detail": f"Error fetching transactions: {e}"}), 500


# --- Unclassified transactions endpoint ---
@app.route("/transactions/unclassified", methods=["GET"])
def get_unclassified():
    limit = request.args.get('limit', default=100, type=int)
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, buchungsdatum, zahlungsempfaenger, verwendungszweck, betrag
            FROM transactions
            WHERE NOT (
                final_category IS NOT NULL
                OR (category_verwendungszweck IS NOT NULL AND TRIM(category_verwendungszweck) <> '' AND LOWER(category_verwendungszweck) <> 'nan')
                OR (category_empfaenger IS NOT NULL AND TRIM(category_empfaenger) <> '' AND LOWER(category_empfaenger) <> 'nan')
                OR (category_pflichtig IS NOT NULL AND TRIM(category_pflichtig) <> '' AND LOWER(category_pflichtig) <> 'nan')
            )
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        txs = [{"id": r[0], "buchungsdatum": r[1], "zahlungsempfaenger": r[2], "verwendungszweck": r[3], "betrag": r[4]} for r in rows]
        return jsonify({"transactions": txs})
    except Exception as e:
        return jsonify({"detail": f"Error fetching transactions: {e}"}), 500


@app.route("/transactions/classify", methods=["POST"])
def classify_transaction():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"detail": "Missing JSON body"}), 400
        transaction_id = payload.get("transaction_id")
        category_type = payload.get("category_type")
        category_id = payload.get("category_id")
        if not all([transaction_id, category_type, category_id]):
            return jsonify({"detail": "Missing fields in JSON body"}), 400
        field_map = {
            "verwendungszweck": "category_verwendungszweck",
            "empfaenger": "category_empfaenger",
            "pflichtig": "category_pflichtig"
        }
        if category_type not in field_map:
            return jsonify({"detail": "Invalid category_type"}), 400
        field = field_map[category_type]
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(f"UPDATE transactions SET {field} = ? WHERE id = ?", (category_id, transaction_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"detail": f"Error updating transaction: {e}"}), 500

# --- DELETE single transaction endpoint ---
@app.route("/transactions/<int:tx_id>", methods=["DELETE"])
def delete_transaction(tx_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        if deleted == 0:
            return jsonify({"detail": f"Transaction {tx_id} not found"}), 404
        return jsonify({"ok": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"detail": f"Error deleting transaction: {e}"}), 500

# --- Bulk delete transactions endpoint ---
@app.route("/transactions/delete_many", methods=["POST"])
def delete_transactions_many():
    try:
        payload = request.get_json()
        if not payload or "ids" not in payload or not isinstance(payload["ids"], list):
            return jsonify({"detail": "JSON body with 'ids' list required"}), 400
        ids = [int(i) for i in payload["ids"] if str(i).isdigit()]
        if not ids:
            return jsonify({"detail": "No valid ids provided"}), 400
        placeholders = ",".join(["?"] * len(ids))
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids)
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return jsonify({"ok": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"detail": f"Error deleting transactions: {e}"}), 500

@app.route("/keywords", methods=["POST"])
def add_keyword():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"detail": "Missing JSON body"}), 400
        keyword = data.get("keyword")
        category = data.get("category")
        subcategory = data.get("subcategory")
        id_ = data.get("id")
        if not all([keyword, category, subcategory, id_]):
            return jsonify({"detail": "Missing fields in JSON body"}), 400
        keywords[keyword] = {"category": category, "subcategory": subcategory, "id": id_}
        with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"detail": f"Error adding keyword: {e}"}), 500

@app.route("/categories", methods=["GET"])
def get_categories():
    try:
        return jsonify(categories)
    except Exception as e:
        return jsonify({"detail": f"Error loading categories: {e}"}), 500

@app.route("/summary_spendings", methods=["GET"])
def get_summary_spendings():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Alle Transaktionen mit gültiger Kategorie-ID (egal ob Verwendungszweck, Empfaenger oder Pflichtig)
        cur.execute("""
            SELECT 
                COALESCE(category_verwendungszweck, category_empfaenger, category_pflichtig) AS cat_id,
                buchungsdatum,
                verwendungszweck,
                betrag
            FROM transactions
            WHERE (
                (category_verwendungszweck IS NOT NULL AND TRIM(category_verwendungszweck) <> '' AND LOWER(category_verwendungszweck) <> 'nan')
                OR (category_empfaenger IS NOT NULL AND TRIM(category_empfaenger) <> '' AND LOWER(category_empfaenger) <> 'nan')
                OR (category_pflichtig IS NOT NULL AND TRIM(category_pflichtig) <> '' AND LOWER(category_pflichtig) <> 'nan')
            )
        """)
        rows = cur.fetchall()

        summary = {"EINKOMMEN": {}, "AUSGABEN": {}}

        def find_category_group_and_subcat(cat_id):
            for cat_type in ["EINKOMMEN", "AUSGABEN"]:
                for group_name, subcats in categories.get(cat_type, {}).items():
                    for subcat in subcats:
                        if str(subcat["id"]) == str(cat_id):
                            return cat_type, group_name, subcat["name"]
            return None, None, None

        for cat_id, buchungsdatum, verwendungszweck, betrag_str in rows:
            cat_type, group_name, subcat_name = find_category_group_and_subcat(cat_id)
            if cat_type is None:
                print(f"WARNING: Kategorie-ID {cat_id} nicht gefunden in categories.json")
                continue
            # Betrag in float konvertieren (z.B. "1.234,56" → 1234.56)
            betrag = parse_betrag(betrag_str)
            # Sign-Normalisierung: Ausgaben negativ, Einkünfte positiv
            if cat_type == "AUSGABEN" and betrag > 0:
                betrag = -betrag
            elif cat_type == "EINKOMMEN" and betrag < 0:
                betrag = -betrag
            # Initialisiere group & subcat im summary dict, falls nicht vorhanden
            if group_name not in summary[cat_type]:
                summary[cat_type][group_name] = {}
            if subcat_name not in summary[cat_type][group_name]:
                summary[cat_type][group_name][subcat_name] = {"summe": 0.0, "entries": []}

            # Werte addieren und Einträge sammeln
            summary[cat_type][group_name][subcat_name]["summe"] += betrag
            summary[cat_type][group_name][subcat_name]["entries"].append({
                "Datum": buchungsdatum,
                "Verwendungszweck": verwendungszweck,
                "Betrag": betrag,
            })

        conn.close()
        return jsonify(summary)

    except Exception as e:
        return jsonify({"detail": f"Error generating summary: {e}"}), 500

@app.route("/summary_spendings_monthly", methods=["GET"])
def get_summary_spendings_monthly():
    try:
        # Query-Param: type = all | expenses | incomes
        filter_type = (request.args.get("type") or "all").lower()

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Lade alle relevanten Transaktionen (ohne SUM(), ohne CAST)
        cur.execute("""
            SELECT 
                COALESCE(category_verwendungszweck, category_empfaenger, category_pflichtig) AS cat_id,
                buchungsdatum,
                betrag
            FROM transactions
            WHERE (
                (category_verwendungszweck IS NOT NULL AND TRIM(category_verwendungszweck) <> '' AND LOWER(category_verwendungszweck) <> 'nan')
                OR (category_empfaenger IS NOT NULL AND TRIM(category_empfaenger) <> '' AND LOWER(category_empfaenger) <> 'nan')
                OR (category_pflichtig IS NOT NULL AND TRIM(category_pflichtig) <> '' AND LOWER(category_pflichtig) <> 'nan')
            )
        """)
        rows = cur.fetchall()

        # Hilfsfunktion: liefert (cat_type, cat_name) für cat_id
        def find_cat_type_and_name(cat_id):
            for cat_type in ["EINKOMMEN", "AUSGABEN"]:
                for group_name, subcats in categories.get(cat_type, {}).items():
                    for subcat in subcats:
                        if str(subcat["id"]) == str(cat_id):
                            return cat_type, subcat["name"]
            return None, None

        # Aggregation: getrennt nach Typ
        by_type = {"EINKOMMEN": {}, "AUSGABEN": {}}
        months_set = set()

        for cat_id, buchungsdatum, betrag_str in rows:
            year_month = to_year_month(buchungsdatum)
            if not year_month:
                continue

            cat_type, cat_name = find_cat_type_and_name(cat_id)
            if not cat_type or not cat_name:
                continue

            amount = parse_betrag(betrag_str)
            # Sign-Normalisierung: Ausgaben negativ, Einkünfte positiv
            if cat_type == "AUSGABEN" and amount > 0:
                amount = -amount
            elif cat_type == "EINKOMMEN" and amount < 0:
                amount = -amount

            months_set.add(year_month)
            if cat_name not in by_type[cat_type]:
                by_type[cat_type][cat_name] = {}
            by_type[cat_type][cat_name][year_month] = by_type[cat_type][cat_name].get(year_month, 0.0) + amount

        months = sorted(months_set)

        # Hilfsfunktion zum Bauen der Chart-Datenstruktur
        def to_chart_payload(cat_map):
            cats = list(cat_map.keys())
            data = { c: [cat_map[c].get(m, 0.0) for m in months] for c in cats }
            return { "categories": cats, "months": months, "data": data }

        # Filter anwenden
        if filter_type == "incomes":
            payload = { "incomes": to_chart_payload(by_type["EINKOMMEN"]) }
        elif filter_type == "expenses":
            payload = { "expenses": to_chart_payload(by_type["AUSGABEN"]) }
        else:
            payload = {
                "expenses": to_chart_payload(by_type["AUSGABEN"]),
                "incomes":  to_chart_payload(by_type["EINKOMMEN"])
            }

        conn.close()
        return jsonify(payload)

    except Exception as e:
        return jsonify({"detail": f"Error generating monthly summary: {e}"}), 500


# --- Raw transactions by month & category ---
@app.route("/transactions/by_month_category", methods=["GET"])
def get_transactions_by_month_category():
    """Return raw transactions for a given month (YYYY-MM) and subcategory name.
    Query params:
      - type: expenses | incomes (default: expenses)
      - category: subcategory display name (e.g., "Miete")
      - ym: year-month in format YYYY-MM
    """
    try:
        cat_name = request.args.get("category")
        ym = request.args.get("ym")  # format YYYY-MM
        req_type = (request.args.get("type") or "expenses").lower().strip()
        # Map to our category root keys
        if req_type.startswith("inc"):
            filt_type = "EINKOMMEN"
        else:
            filt_type = "AUSGABEN"

        if not cat_name or not ym or len(ym) != 7 or ym[4] != '-':
            return jsonify({"detail": "Query params 'category' and 'ym' (YYYY-MM) required"}), 400

        # resolve category id by name + type (case/whitespace-insensitive)
        def resolve_cat_id(catname: str, cat_type: str) -> Optional[str]:
            target = str(catname).strip().casefold()
            for group_name, subcats in categories.get(cat_type, {}).items():
                for sub in subcats:
                    if str(sub.get("name", "")).strip().casefold() == target:
                        # return as TEXT to be robust vs TEXT-stored ids
                        return str(sub.get("id"))
            return None

        cat_id = resolve_cat_id(cat_name, filt_type)
        if cat_id is None:
            return jsonify({"detail": f"Category '{cat_name}' not found in {filt_type}"}), 404

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Hole alle Zeilen für die Kategorie; Monatsfilter erfolgt robust in Python
        cur.execute(
            """
            SELECT buchungsdatum, verwendungszweck, zahlungsempfaenger, betrag
            FROM transactions
            WHERE CAST(COALESCE(category_verwendungszweck, category_empfaenger, category_pflichtig) AS TEXT) = ?
            ORDER BY buchungsdatum
            """,
            (str(cat_id),)
        )
        rows = cur.fetchall()
        conn.close()

        entries = []
        total = 0.0
        months_available_set = set()
        for d, vz, empf, betrag_str in rows:
            year_month = to_year_month(d)
            if year_month:
                months_available_set.add(year_month)
            if year_month != ym:
                continue
            amt = parse_betrag(betrag_str)
            entries.append({
                "date": d,
                "description": vz or empf or "",
                "amount": amt
            })
            total += amt

        return jsonify({
            "category": cat_name,
            "year_month": ym,
            "type": filt_type,
            "total": total,
            "count": len(entries),
            "months_available": sorted(months_available_set),
            "entries": entries
        })
    except Exception as e:
        return jsonify({"detail": f"Error fetching details: {e}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)