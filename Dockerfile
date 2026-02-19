FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# This copies everything from your local folder into the /app folder in the container
COPY . .

CMD ["python", "bot.py"]