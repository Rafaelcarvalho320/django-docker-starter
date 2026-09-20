# syntax=docker/dockerfile:1

# ---- build stage -----------------------------------------------------------
# Wheels are compiled once here so the runtime image needs no build toolchain,
# which is both smaller and a smaller attack surface.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt


# ---- runtime stage ---------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# A container process running as root is one file-write bug away from being
# host root. Created before the copy so ownership can be set in one step.
RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=app:app . .

# Belt and braces: the repository also carries the executable bit, but a
# clone made on a filesystem that does not track it would otherwise produce
# an image that dies at startup with "permission denied".
RUN chmod +x entrypoint.sh

# Static files are collected at build time, not at boot: it is the same result
# every time, so doing it per container start would only slow every deploy and
# risk two replicas disagreeing. The key here is a build-time placeholder;
# collectstatic never reads it, and it never reaches the running container.
RUN DJANGO_SECRET_KEY=build-time-only \
    DJANGO_DEBUG=false \
    python manage.py collectstatic --noinput --clear

USER app

EXPOSE 8000

# Liveness only: this must not touch the database, or a database blip would
# make the runtime kill every otherwise-healthy container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live/', timeout=3).status == 200 else 1)"

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
