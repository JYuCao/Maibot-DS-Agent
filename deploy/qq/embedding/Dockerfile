FROM python:3.13-slim
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
ENV HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
