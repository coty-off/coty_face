FROM python:3.11-slim

WORKDIR /app

# Минимальные системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "numpy<2.0"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY project/ ./project/
COPY coty/ ./coty/

RUN mkdir -p /uploads /photos

EXPOSE 8000

CMD ["tail", "-f", "/dev/null"]