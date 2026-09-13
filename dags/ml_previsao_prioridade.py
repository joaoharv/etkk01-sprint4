"""DAG de inferencia do modelo de classificacao de Prioridade (Plano 2.1, Etapa 12).

So ORQUESTRA o pipeline ja implementado e testado na Etapa 11 -- nenhuma
logica de ML, feature engineering, metrica ou SQL de persistencia vive aqui.
Uma unica task, pelo mesmo motivo da DAG de volume (ml_previsao_volume.py):
gerar_previsoes_prioridade() ja garante, por construcao, que as previsoes e a
avaliacao OOS vem exatamente da mesma chamada de .predict()/.decision_function()
-- separar isso em varias tasks exigiria trafegar o DataFrame por XCom
(proibido nesta arquitetura) ou recalcular a populacao em cada task.

Nao treina nada -- o modelo ja foi treinado e promovido em models/prioridade/
(Etapa 11, script manual). Nao depende formalmente de pipeline_incidentes_ti
nem de ml_previsao_volume (sem ExternalTaskSensor, por decisao do Plano 2.1).

Classificacao RETROSPECTIVA sobre historico estatico -- nao ha "forward"
(diferente do modelo de volume): todo incidente da populacao ja tem uma
Prioridade real conhecida. gold.previsoes_prioridade so recebe VAL+TEST (a
fatia fora do treino do artefato persistido) -- nunca TRAIN.

    docker compose exec airflow-webserver airflow dags trigger ml_previsao_prioridade
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

from config.logging import get_logger
from src.load.load_previsoes import load_previsoes_prioridade
from src.ml.predict_prioridade import gerar_previsoes_prioridade

log = get_logger(__name__)

_DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="ml_previsao_prioridade",
    description="Classificacao retrospectiva de Prioridade (LinearSVC, piloto assistido) em gold.previsoes_prioridade",
    schedule=None,  # disparo manual
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    default_args=_DEFAULT_ARGS,
    tags=["sprint4", "ml", "prioridade"],
)
def ml_previsao_prioridade():

    @task
    def executar_predict_prioridade() -> dict:
        previsoes, metricas_oos = gerar_previsoes_prioridade()
        n = load_previsoes_prioridade(previsoes)
        log.info(
            "gold.previsoes_prioridade: %d linha(s) upsertadas | avaliacao OOS: %s",
            n, metricas_oos,
        )
        return {"linhas_gravadas": n, "metricas_oos": metricas_oos}

    executar_predict_prioridade()


ml_previsao_prioridade()
