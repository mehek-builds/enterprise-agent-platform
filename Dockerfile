FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

COPY app/ app/
COPY evals/ evals/
COPY stress/ stress/
COPY CHANGELOG.md .

# All configuration is env-var driven: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY,
# JWT_SECRET, role API keys, OTEL_EXPORTER_OTLP_ENDPOINT. No cloud-specific
# dependencies; runs identically on Azure Container Apps, AKS, or any VPS.
ENV AUDIT_DB_PATH=/srv/data/audit.db \
    CHECKPOINT_DB_PATH=/srv/data/checkpoints.db
RUN mkdir -p /srv/data
VOLUME /srv/data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/health').raise_for_status()"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
