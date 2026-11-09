# Optional. The controller has two runtime dependencies (httpx, pyyaml) and uses SQLite from the standard library.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir httpx pyyaml
COPY controller ./controller
ENV PYTHONHASHSEED=0 PYTHONUNBUFFERED=1
VOLUME /app/state
ENTRYPOINT ["python", "-m", "controller.main", "--db", "/app/state/controller.db", "--archive", "/app/state/exposure_archive", "--url"]
