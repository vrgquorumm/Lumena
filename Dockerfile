FROM python:3.11-slim

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY bot/ ./bot/

# Рабочая директория — папка бота (все пути data/ относительны)
WORKDIR /app/bot

# Создаём папку для данных
RUN mkdir -p data

CMD ["python", "bot.py"]
