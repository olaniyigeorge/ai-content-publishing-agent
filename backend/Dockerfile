# Shared image for both long-running backend processes — the API
# (uvicorn) and the worker (polling loop). Which one runs is picked by the
# CMD override in docker-compose.yml / your platform's process command.
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg[binary]'s wheel and general TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY auth ./auth
COPY claude ./claude
COPY db ./db
COPY shared ./shared
COPY worker ./worker
COPY alembic ./alembic
COPY alembic.ini ./
COPY render-entrypoint.sh ./

RUN pip install --no-cache-dir . \
    && chmod +x render-entrypoint.sh

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# docker-compose overrides this with an explicit `command:` per service
# (see docker-compose.yml) — this default is for single-container hosts
# like Render's free tier, which runs api + worker together.
CMD ["./render-entrypoint.sh"]
