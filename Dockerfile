FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run continuous 5m monitoring loop with trend-change alert filtering
CMD ["python", "main.py", "--watch", "--interval", "300", "--send-telegram", "--alert-on-trend-change-only", "--output", "console"]
