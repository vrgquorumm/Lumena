FROM python:3.11-slim

WORKDIR /app

# Залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код бота
COPY . .

# Railway встановлює $PORT автоматично
ENV PORT=8080

CMD ["bash", "start.sh"]
