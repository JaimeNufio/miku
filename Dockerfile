FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

RUN useradd --create-home --shell /usr/sbin/nologin miku
USER miku

CMD ["python", "-m", "bot.main"]
