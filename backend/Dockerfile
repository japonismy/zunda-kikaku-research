FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend /app/backend
COPY data/catalog.js /app/data/catalog.js
ENV PYTHONUNBUFFERED=1
CMD ["python", "backend/run_daily.py"]
