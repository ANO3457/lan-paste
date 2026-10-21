FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --system --uid 10001 --create-home appuser && mkdir -p /data && chown -R appuser:appuser /data /app
COPY --chown=appuser:appuser . .
EXPOSE 8000
# Named Docker volumes are initially root-owned; fix ownership, then drop privileges.
CMD ["sh", "-c", "chown appuser:appuser /data && exec su -s /bin/sh appuser -c 'gunicorn --workers 2 --threads 4 --bind 0.0.0.0:8000 --access-logfile - app:app'"]
