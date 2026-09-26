FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv/bolorder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 bolorder \
    && mkdir /data && chown bolorder:bolorder /data
COPY --chown=bolorder:bolorder app ./app
USER bolorder
ENV DATABASE_PATH=/data/bolorder.sqlite3 PUBLIC_DEPLOYMENT=true
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers"]
