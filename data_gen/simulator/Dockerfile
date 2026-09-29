FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn[standard] pyyaml pydantic

COPY data_gen/ data_gen/

EXPOSE 8100

ENTRYPOINT ["python", "-m", "data_gen.simulator"]
CMD ["--config", "data_gen/simulator/default_config.yml"]
