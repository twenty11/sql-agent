FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY alembic.ini config.py server.py ./
COPY alembic ./alembic
COPY api ./api
COPY auth ./auth
COPY db ./db
COPY graph ./graph
COPY scripts ./scripts
COPY services ./services
COPY tasks ./tasks
COPY utils ./utils
COPY vectorstore ./vectorstore

RUN mkdir -p /app/upload_staging /app/logs

EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
