FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY project/ ./project/
COPY coty/ ./coty/

# Если в проекте есть __pycache__ и т.п. — можно игнорировать через .dockerignore
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]