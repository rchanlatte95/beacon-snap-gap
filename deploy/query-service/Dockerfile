# QueryService for Cloud Run (REQ-38, REQ-43, REQ-46, REQ-49, REQ-50, REQ-52, Z-8, Z-19)
# Base image: Python 3.12 slim. Dependencies installed via uv frozen sync without dev tools.
# Runs as non-root user. PORT supplied by Cloud Run (default 8080).

FROM python:3.12-slim

# Copy uv binary from official multi-arch image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create runtime user and directories
ENV APP_USER=appuser
ENV APP_HOME=/home/appuser
ENV REPO_ROOT=/app

RUN groupadd --system --gid 1001 "${APP_USER}" \
    && useradd --system --uid 1001 --gid 1001 --create-home --home-dir "${APP_HOME}" "${APP_USER}"

WORKDIR ${REPO_ROOT}

# Install dependencies into virtualenv using uv
COPY pyproject.toml uv.lock ./

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN uv sync --frozen --no-dev --no-install-project

# Preinstall DuckDB spatial extension as the runtime user so it is cached in ${APP_HOME}/.duckdb/extensions/
# and available offline without internet access or runtime download when GEOMETRY columns are queried.
USER ${APP_USER}
RUN python -c "import duckdb; duckdb.connect().execute('INSTALL spatial')"

# Switch to root to copy source tree and docs/taxonomy.md (read by server.py / answer.py at REPO_ROOT/docs/taxonomy.md)
USER root
COPY src/ ${REPO_ROOT}/src/
COPY docs/taxonomy.md ${REPO_ROOT}/docs/taxonomy.md

RUN chown -R ${APP_USER}:${APP_USER} ${REPO_ROOT}

# Drop privileges to runtime user
USER ${APP_USER}

# Port configuration (Cloud Run sets PORT environment variable, defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# Entrypoint: python -m src.query_service.server
CMD ["python", "-m", "src.query_service.server"]
