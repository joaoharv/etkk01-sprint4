"""DAG do pipeline Medallion dos incidentes de TI (LW-DATASET).

A DAG apenas orquestra: cada task chama uma funcao de ``src/`` e registra a
contagem processada. Nenhuma logica de negocio vive aqui. Nao trafega DataFrame
por XCom — cada task rele a camada anterior direto do Postgres.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.decorators import dag, task

from config.logging import get_logger
from src.db import read_table, run_sql_file
from src.extract.read_source import read_source
from src.load.load_bronze import load_bronze
from src.load.load_gold import load_gold
from src.load.load_silver import load_silver
from src.transform.aggregate_gold import build_gold
from src.transform.clean_incidentes import clean
from src.validation.checks import validate_pipeline as run_validacoes

log = get_logger(__name__)

_SQL_CREATE = Path("/opt/airflow/project/sql/create")

_DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="pipeline_incidentes_ti",
    description="ETL Medallion dos incidentes de TI (LW-DATASET): Bronze -> Silver -> Gold",
    schedule=None,  # fonte estatica: disparo manual
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    default_args=_DEFAULT_ARGS,
    tags=["sprint4", "medallion"],
)
def pipeline_incidentes_ti():

    @task
    def create_schema() -> None:
        arquivos = sorted(_SQL_CREATE.glob("*.sql"))
        if not arquivos:
            raise FileNotFoundError(f"Nenhum script SQL em {_SQL_CREATE}")
        for arquivo in arquivos:
            run_sql_file(arquivo)
        log.info("create_schema: %d scripts aplicados", len(arquivos))

    @task
    def extract_bronze() -> int:
        n = load_bronze(read_source())
        log.info("Bronze carregada: %d linhas", n)
        return n

    @task
    def transform_silver() -> int:
        n = load_silver(clean(read_table("incidentes_raw", "bronze")))
        log.info("Silver carregada: %d linhas", n)
        return n

    @task
    def transform_gold() -> dict[str, int]:
        resultado = load_gold(build_gold(read_table("incidentes_tratados", "silver")))
        log.info("Gold carregada: %s", resultado)
        return resultado

    @task
    def validate_pipeline() -> None:
        run_validacoes()

    (
        create_schema()
        >> extract_bronze()
        >> transform_silver()
        >> transform_gold()
        >> validate_pipeline()
    )


pipeline_incidentes_ti()
