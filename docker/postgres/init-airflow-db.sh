#!/bin/bash
# Executado uma unica vez, na primeira inicializacao do container Postgres.
# Cria um banco separado para os metadados do Airflow, mantendo o banco de
# negocio "incidentes_ti" (POSTGRES_DB) livre das tabelas internas do orquestrador.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
    GRANT ALL PRIVILEGES ON DATABASE airflow TO "$POSTGRES_USER";
EOSQL

echo "[init] banco 'airflow' (metadados) verificado/criado."
