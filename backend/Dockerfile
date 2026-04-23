# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Install uv from the official image (best practice)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Python optimizations for Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files first (critical for layer caching)
COPY pyproject.toml ./

RUN uv lock

# Install dependencies only (no dev group, no editable install for production)
# This layer is cached unless pyproject.toml or uv.lock changes
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# Now copy the application code
COPY . .

# Install the project itself (your code)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

# Run with uvicorn (uv will use the managed environment)
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]