# Imagem customizada do Airflow: base oficial + dependencias da camada ETL (src/).
FROM apache/airflow:2.9.3-python3.11

# curl e usado pelo healthcheck do webserver no docker-compose.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER airflow

# Instala as dependencias do ETL respeitando o constraint do Airflow 2.9.3,
# evitando quebrar as versoes que a imagem base ja resolve (SQLAlchemy < 2, etc).
# O provider apache-airflow-providers-postgres ja vem na imagem base.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.11.txt"
