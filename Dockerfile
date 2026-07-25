FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MAWI_LLM_ENABLED=false \
    MAWI_DEMO_MODE=true \
    MAWI_API_AUTH_MODE=protected \
    MAWI_DB_PATH=/data/mawi.db

WORKDIR /app
COPY . .
RUN python -m pip install --no-cache-dir .

RUN mkdir -p /data && chown -R 10001:10001 /app /data
USER 10001

EXPOSE 8000
CMD ["sh", "-c", "if [ -z \"$MAWI_API_BEARER_TOKEN\" ]; then echo >&2 'MAWI_API_BEARER_TOKEN is required for the protected demo'; exit 1; fi; exec uvicorn api.app:create_web_app --factory --host 0.0.0.0 --port 8000"]
