FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/RyanJoo28/enc-chat" \
      org.opencontainers.image.description="Enc Chat backend image" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装阶段
# 安装构建部分 Python 依赖所需的系统包。
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

# requirements.txt 采用 UTF-16 LE，需要先转成 UTF-8 再安装。
RUN python - <<'PY'
from pathlib import Path

source = Path('/tmp/requirements.txt')
target = Path('/tmp/requirements.utf8.txt')
target.write_text(source.read_text(encoding='utf-16'), encoding='utf-8')
PY

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.utf8.txt \
    && rm -f /tmp/requirements.txt /tmp/requirements.utf8.txt

# 运行阶段
# 仅复制运行时所需源码和入口脚本。
COPY app ./app
COPY audit_encryption.py ./audit_encryption.py
COPY docker-entrypoint.sh /usr/local/bin/backend-entrypoint.sh

RUN chmod +x /usr/local/bin/backend-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["backend-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
