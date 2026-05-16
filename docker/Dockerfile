FROM python:3.11-slim

WORKDIR /app

COPY ../src/conversational-agent-open-api/* .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
