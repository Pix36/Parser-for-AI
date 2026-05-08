FROM python:3.11-slim

# Crea la cartella base nel container
WORKDIR /app

COPY frontend/requirements.txt ./frontend/
RUN pip install --no-cache-dir -r frontend/requirements.txt

# Copia la cartella src (che contiene frontend.py) all'interno del container
COPY frontend/ ./frontend/

# Spostati nella cartella src dove risiede effettivamente il file frontend.py
WORKDIR /app/frontend/src

EXPOSE 8004

CMD ["uvicorn", "frontend:app", "--host", "0.0.0.0", "--port", "8004"]