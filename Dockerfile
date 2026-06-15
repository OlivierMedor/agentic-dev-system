FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && CODEX_NON_INTERACTIVE=1 CODEX_INSTALL_DIR=/usr/local/bin sh -c 'curl -fsSL https://chatgpt.com/codex/install.sh | sh' \
    && codex --version \
    && git config --system --add safe.directory /app \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

RUN python -m pip install --upgrade pip \
    && pip install -e ".[dev]"

CMD ["bash"]
