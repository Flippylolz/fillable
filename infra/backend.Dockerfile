FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt && useradd --uid 10001 --create-home app && chown app:app /app
COPY --chown=app:app backend/ ./
COPY --chown=app:app scripts/ /checks/
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
