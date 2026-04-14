FROM python:3.11-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Фиксируем NumPy
RUN pip install --no-cache-dir "numpy==1.26.4"

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY api/ ./api/
COPY coty/ ./coty/
COPY project/face_parsing/ ./project/face_parsing/

RUN mkdir -p /uploads /photos

EXPOSE 8000

CMD ["tail", "-f", "/dev/null"]