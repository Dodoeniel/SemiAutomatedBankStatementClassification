FROM python:3.11-slim

# System-Dependencies für pdfplumber/pandas
RUN apt-get update && apt-get install -y build-essential poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App rein
COPY . /app

# Gunicorn in Produktion
ENV PORT=8000
EXPOSE 8000
CMD ["gunicorn", "-w", "3", "-k", "gthread", "-b", "0.0.0.0:8000", "app:app", "--forwarded-allow-ips=*"]