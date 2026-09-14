"""DAG de inferencia do modelo de volume (Plano 2.1, Etapa 9).

So ORQUESTRA o pipeline ja implementado e testado na Etapa 8 -- nenhuma logica
de ML, feature engineering, metrica ou SQL de persistencia vive aqui. Uma
unica task, de proposito: gerar_previsoes_volume() ja garante, por construcao,
que o backfill e a avaliacao OOS usam exatamente a mesma previsao (mesma
chamada de .predict()); separar isso em varias tasks do Airflow exigiria
trafegar o DataFrame de features por XCom (proibido nesta arquitetura, mesma
regra da DAG do ETL) ou recalcular o dataset em cada task (duplicaria a
consulta ao Postgres e arriscaria inconsistencia entre backfill e avaliacao
se a Silver mudasse no meio do caminho).

Nao treina nada -- o modelo ja foi treinado e promovido em models/volume_d7/
(Etapa 7, script manual). Nao depende formalmente de pipeline_incidentes_ti
(sem ExternalTaskSensor, por decisao do Plano 2.1): rode esta DAG depois do
ETL principal ter concluido, nao em paralelo.

    docker compose exec airflow-webserver airflow dags trigger ml_previsao_volume
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

from config.logging import get_logger
from src.alertas.notificacoes import notificar_falha_operacional
from src.load.load_previsoes import load_previsoes_volume
from src.ml.alertas_threshold import calcular_e_registrar_thresholds_volume
from src.ml.predict_volume import gerar_previsoes_volume

log = get_logger(__name__)

_DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    # Alerta operacional por e-mail (Plano 2.1, Etapa 15) -- so na falha
    # definitiva (todas as tentativas esgotadas), nunca a cada retry.
    "on_failure_callback": notificar_falha_operacional,
}


@dag(
    dag_id="ml_previsao_volume",
    description="Inferencia do modelo de volume (D+1 persistencia, D+7 Ridge) em gold.previsoes",
    schedule=None,  # disparo manual, depois do ETL principal ja ter rodado
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    default_args=_DEFAULT_ARGS,
    tags=["sprint4", "ml", "volume"],
)
def ml_previsao_volume():

    @task
    def executar_predict_volume() -> dict:
        previsoes, metricas_oos = gerar_previsoes_volume()
        n = load_previsoes_volume(previsoes)
        if n == 0:
            # "Previsoes ausentes" vira falha definitiva da task -- reaproveita
            # o alerta operacional ja existente (on_failure_callback), sem
            # precisar de nenhuma tabela/mecanismo novo de deteccao (Etapa 15).
            raise RuntimeError(
                "gerar_previsoes_volume() nao produziu nenhuma linha -- "
                "gold.previsoes ficaria sem previsao nesta execucao."
            )
        log.info(
            "gold.previsoes: %d linha(s) upsertadas | avaliacao OOS (D+7): %s",
            n, metricas_oos,
        )
        thresholds = calcular_e_registrar_thresholds_volume(metricas_oos)
        log.info("Thresholds de alerta (Grafana) registrados: %s", thresholds)
        return {"linhas_gravadas": n, "metricas_oos_d7": metricas_oos, "thresholds": thresholds}

    executar_predict_volume()


ml_previsao_volume()
