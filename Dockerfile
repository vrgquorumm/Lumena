FROM python:3.11-slim

WORKDIR /app

# Install the bot and website runtime dependencies.
COPY bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# The bot package also contains the static website and shared startup script.
COPY bot/ /app/
RUN chmod +x /app/start.sh

ENV PYTHONUNBUFFERED=1

# Start the website on Railway's $PORT and run the Telegram bot alongside it.
CMD ["bash", "/app/start.sh"]
