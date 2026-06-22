FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /bin/

ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache \
    TRANSFORMERS_CACHE=/opt/hf-cache \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    EMBEDDING_MODEL=${EMBEDDING_MODEL}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --extra semantic --no-install-project \
    && uv cache clean


# RUN mkdir -p /opt/hf-cache \
#     && .venv/bin/python -c "from sentence_transformers import SentenceTransformer; import os; SentenceTransformer(os.environ['EMBEDDING_MODEL'], cache_folder=os.environ['HF_HOME'])"


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TRANSFORMERS_OFFLINE=0 \
    TOKENIZERS_PARALLELISM=false \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app /opt/hf-cache \
    && chown -R app:app /app /opt/hf-cache

COPY --from=builder --chown=app:app /app/.venv /app/.venv

RUN mkdir -p /opt/hf-cache && chown -R app:app /opt/hf-cache

COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
