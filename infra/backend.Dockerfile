FROM python:3.15.0-slim-bookworm@sha256:0e019bbdfb5d9874cb2389f1c2884b64aa2ac97c99960b5bc521cef978c0617d
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt && useradd --uid 10001 --create-home app && chown app:app /app
COPY --chown=app:app backend/ ./
COPY --chown=app:app scripts/ /checks/
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
