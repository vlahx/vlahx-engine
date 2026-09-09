FROM python:3.14-slim

WORKDIR /app

# Runtime dependencies for Pillow & web tools
RUN apt-get update     && apt-get install -y --no-install-recommends         libjpeg62-turbo         libopenjp2-7         libwebp7         libtiff6     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV APP_PORT=8000

EXPOSE 8000

CMD ["python", "run.py"]
