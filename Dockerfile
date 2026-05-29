FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8060
ENV PIPE_CCTV_DATA_DIR=/app/data

EXPOSE 8060

CMD ["python", "app.py"]
