# Збирається з кореня репозиторію: docker build -f app/Dockerfile .
# (так handler.py береться з lambda/ без копіювання коду)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --no-create-home --uid 10001 app

COPY lambda/handler.py app/server.py app/init_table.py ./

USER app
EXPOSE 8000

# у slim-образі немає curl, тому перевірка через stdlib; /health не звертається до DynamoDB
HEALTHCHECK --interval=5s --timeout=2s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["python", "server.py"]
