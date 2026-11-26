FROM python:3.13-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50 AS build
ENV UV_COMPILE_BYTECODE=0 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
RUN pip install --no-cache-dir uv==0.13.10
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FDH_CONFIG=/app/config/sources.toml
RUN useradd --system --uid 10001 --no-create-home fdh
WORKDIR /app
COPY --from=build /app/.venv ./.venv
COPY alembic.ini ./
COPY migrations ./migrations
# The sources configuration is mounted read-only at run time; it is never part of the image.
USER 10001
EXPOSE 8000
CMD ["uvicorn", "fdh.api.app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
