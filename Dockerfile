# syntax=docker/dockerfile:1
#
# Multi-stage build for the AIOps control API.
#   - builder stage: resolves dependencies into an isolated virtualenv
#   - runtime stage: copies only the venv + app code, runs as a non-root user
# The split keeps the final image small (no build toolchain) and cache-friendly.

ARG PYTHON_VERSION=3.11-slim

# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Isolated virtualenv we can copy wholesale into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only what the package build needs, then install.
# (pyproject first would cache better, but the build backend needs the sources
#  present to discover packages, so we copy them together.)
COPY pyproject.toml ./
COPY app ./app
COPY evals ./evals
COPY simulator ./simulator
RUN pip install .

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as an unprivileged user (least privilege; never root in a container).
RUN groupadd --system app && useradd --system --gid app --no-create-home appuser

WORKDIR /app

# Dependencies (prebuilt venv) + application code + migration assets.
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

USER appuser

EXPOSE 8000

# Liveness probe using stdlib only (slim image has no curl/wget).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
