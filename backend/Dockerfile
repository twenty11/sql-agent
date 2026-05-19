# ==================== Backend Dockerfile - 生产环境 ====================
FROM python:3.12-slim

# 环境变量优化
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_VERSION=2.11.0

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（先复制 requirements 利用 Docker 缓存）
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --index-url ${PYTORCH_INDEX_URL} torch==${TORCH_VERSION} \
    && pip install --no-cache-dir -r requirements.txt

# 复制后端全部代码
COPY backend/ ./

# 创建必要目录并设置权限
RUN mkdir -p /app/upload_staging /app/logs \
    && chmod -R 755 /app/upload_staging /app/logs

EXPOSE 8080

# 使用 Gunicorn + Uvicorn 作为生产服务器（更稳定，支持 workers）
CMD ["gunicorn", \
     "server:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8080", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--log-level", "info"]
