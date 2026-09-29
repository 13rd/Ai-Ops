FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "sqlalchemy>=2.0" \
    "psycopg2-binary>=2.9" \
    "pandas>=2.0" \
    "pydantic>=2.5" \
    "pydantic-settings>=2.1"

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "data_gen/trainbed/generator.py"]
