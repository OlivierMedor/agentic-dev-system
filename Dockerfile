FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

COPY scripts ./scripts

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && sh /app/scripts/install_codex_cli.sh \
    && git config --system --add safe.directory /app \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

RUN python -m pip install --upgrade pip \
    && pip install -e ".[dev]"

CMD ["bash"]
