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

### Umgebungsvariablen

Für das Frontend wird eine `.env` Datei im Verzeichnis `01_frontend/` benötigt. Beispiel:

```env
VITE_API_BASE=/api
```

Optional kann im Backend eine `.env` Datei im Verzeichnis `backend/` angelegt werden, z.B.:

```env
DB_PATH=database.db
FLASK_ENV=production
```

### Backend (lokal)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port 8000
```

### Frontend (lokal)

```bash
cd frontend
npm install
npm run dev
```

### Mit Docker Compose

```bash
docker compose up -d --build
```

Hinweis: Nginx leitet die Requests an das Frontend (Port 5080) und Backend (Port 5800) weiter.

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
├── frontend/          # Vue 3 + Vuetify Frontend
└── README.md             # Diese Datei
```

## ToDo

- Export-Funktion (CSV/Excel)
- Mehr Visualisierungen
- Bessere Autoklassifikation