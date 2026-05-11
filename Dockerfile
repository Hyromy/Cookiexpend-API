FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /home/app

RUN useradd -m -u 1000 appuser

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir poetry

COPY --chown=appuser:appuser pyproject.toml poetry.lock* ./

RUN mkdir -p /home/app/staticfiles \
    && chown -R appuser:appuser /home/app/staticfiles

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "\
    python manage.py migrate --no-input && \
    python manage.py collectstatic --no-input && \
    gunicorn project.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 2 \
        --worker-class gevent \
        --worker-tmp-dir /dev/shm \
        --timeout 120 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --access-logfile - \
        --error-logfile - \
"]
