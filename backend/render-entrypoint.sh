#!/bin/sh
# Render's free tier only offers Web Services, not Background Workers, so
# the worker polling loop runs as a background process inside the same
# container as the API. Render only ever sees one process bound to $PORT.
set -e

python -m worker.main &

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
