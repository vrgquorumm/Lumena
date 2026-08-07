FROM python:3.11-slim

WORKDIR /app/bot

# Залежності з bot/requirements.txt
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Увесь код бота
COPY bot/ .

# Railway встановлює $PORT автоматично
ENV PORT=8080

CMD ["bash", "start.sh"]
