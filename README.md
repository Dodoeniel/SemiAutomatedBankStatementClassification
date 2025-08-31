

# PythonBankStatement

Ein Tool zur Verarbeitung, Analyse und Visualisierung von Bank-Statements (DKB, Revolut, AMEX).  
Frontend: Vue 3 mit Vuetify  
Backend: Python (Flask, SQLite, pandas)

## Features

- Upload von CSV/PDF Dateien (DKB, Revolut, AMEX)
- Automatische Speicherung in SQLite
- Autoklassifikation von Transaktionen
- Manuelle Nachklassifikation im Frontend
- Summary-Ansichten (Monats-, Jahresübersichten)
- Charts und Tabellen für Ausgaben & Einnahmen
- Lösch- und Filterfunktionen

## Installation

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port 8000
```

### Frontend
```bash
cd 01_frontend
npm install
npm run dev
```

## Nutzung

1. Backend starten
2. Frontend starten
3. CSV/PDF hochladen
4. Transaktionen klassifizieren und analysieren

## Projektstruktur

```
PythonBankStatement/
├── backend.py            # Flask Server mit API Endpoints
├── database.db           # SQLite Datenbank
├── 01_frontend/          # Vue 3 + Vuetify Frontend
└── README.md             # Diese Datei
```

## ToDo

- Export-Funktion (CSV/Excel)
- Mehr Visualisierungen
- Bessere Autoklassifikation