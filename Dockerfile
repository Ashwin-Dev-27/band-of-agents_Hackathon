FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uvicorn

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY agents/ agents/
COPY band_integration/ band_integration/
COPY data/ data/
COPY .env.example .env

COPY frontend/dist/ frontend/dist/

ENV DEMO_MODE=true
ENV CORS_ORIGINS=*
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
