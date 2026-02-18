FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py google_drive.py google_sheets.py ./

CMD ["python", "bot.py"]
