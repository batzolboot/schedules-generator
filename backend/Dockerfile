FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# pyproject.toml references ../README.md. The repository README is outside the
# backend-only build context, so provide build metadata at the expected path.
COPY pyproject.toml ./
COPY src ./src
RUN printf '%s\n' '# Drexel Schedule Generator backend' > /README.md \
    && python -m pip install . \
    && rm /README.md

# Keep migrations available for one-off `alembic upgrade head` invocations.
COPY alembic.ini ./
COPY alembic ./alembic

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app app \
    && chown -R app:app /app

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/health', timeout=2)"

CMD ["sh", "-c", "exec uvicorn drexel_schedule_generator.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
