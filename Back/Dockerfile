ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY contracts ./contracts
COPY migrations ./migrations
COPY demo-assets ./demo-assets
COPY alembic.ini ./
RUN python -m pip install --no-cache-dir . \
    && groupadd --gid 10001 commerce \
    && useradd --uid 10001 --gid commerce --no-create-home commerce \
    && mkdir -p /app/.local \
    && chown -R commerce:commerce /app

USER commerce
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
