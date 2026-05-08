FROM python:3.11-slim

WORKDIR /app


COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt


COPY backend/ ./backend/
COPY GS_Data/ ./GS_Data/
COPY domini.json ./

RUN playwright install --with-deps chromium


ENV PYTHONPATH=/app/backend/src


WORKDIR /app/backend/src


CMD ["uvicorn", "rest.Server:app", "--host", "0.0.0.0", "--port", "8003"]