FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Корневой bot.py (точка входа Railway) + весь bot/ (реальный код)
COPY bot.py .
COPY bot/ ./bot/

# Папка для данных внутри bot/ (все пути относительны bot/)
RUN mkdir -p bot/data

CMD ["python", "bot.py"]
