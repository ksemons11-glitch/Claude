# Single application image; compose selects the process via command.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY docs ./docs
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd -r -u 10001 director && mkdir -p /app/var && chown -R director /app/var
USER director
HEALTHCHECK --interval=30s --timeout=5s CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live').status==200 else 1)"] 
CMD ["director", "--help"]
