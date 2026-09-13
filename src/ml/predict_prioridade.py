"""Inferencia do modelo de classificacao de Prioridade (Plano 2.1, Etapa 11).

Diferente do modelo de volume, aqui NAO existe um "forward" genuino: a fonte
e' estatica, todo incidente da populacao ja tem uma Prioridade real conhecida
-- nao ha nada "no futuro" para prever. Por isso este pipeline e' uma
classificacao RETROSPECTIVA (reclassifica o historico), nunca um forecast.

Mesma disciplina de avaliacao do modelo de volume: o pipeline foi ajustado
SO em TRAIN (set+out/2025, ver train_prioridade.py -- o notebook 02 nao tem
refit de producao em TRAIN+VAL). A UNICA fatia genuinamente fora do treino e'
VAL + TEST (nov+dez/2025) -- e' isso, e so isso, que e' escrito em
gold.previsoes_prioridade. Escorar em TRAIN inflaria os numeros com previsao
in-sample (o pipeline ja viu essas descricoes no ajuste).

``score_vencedor`` vem de ``LinearSVC.decision_function()`` -- e' um score de
margem, NAO uma probabilidade. Nunca apresentar como "confianca" ou "%".

O proprio notebook classifica este pipeline como "Experimental" (nao
"Recomendado") -- uso recomendado e' piloto assistido de triagem, com
validacao humana, nunca decisao automatica (ver metadata.json).

Roda como script manual (mesma maturidade de predict_volume.py -- ainda NAO
e' task de DAG):

    docker compose exec airflow-webserver python -m src.ml.predict_prioridade
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.logging import get_logger
from src.ml.features.prioridade_features import (
    CLASSES_ALVO,
    carregar_populacao_prioridade,
    preparar_features_prioridade,
    split_temporal_prioridade,
)
from src.ml.metrics import calcular_metricas_classificacao
from src.ml.model_registry import load_model, validar_features

log = get_logger(__name__)

NOME_MODELO = "prioridade"


def montar_populacao_oos() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Populacao completa + a fatia OOS (VAL+TEST, fora do periodo de treino
    do pipeline persistido). Devolve (populacao_completa, populacao_oos) --
    a completa e' reaproveitada para montar as features na mesma chamada."""
    populacao = carregar_populacao_prioridade()
    _train, val, test = split_temporal_prioridade(populacao)
    oos = populacao.loc[val.index.union(test.index)].sort_values("aberto")
    return populacao, oos


def avaliar_oos_e_prever(modelo, populacao_oos: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Uma unica chamada a .predict()/.decision_function() alimenta as
    previsoes E a metrica de avaliacao -- garante, por construcao, que as
    duas vem exatamente da mesma fatia de dados (mesmo padrao do volume)."""
    X_oos = preparar_features_prioridade(populacao_oos)
    y_oos = populacao_oos["prioridade"]

    pred = modelo.predict(X_oos)
    scores = modelo.decision_function(X_oos)
    classes = modelo.named_steps["modelo"].classes_
    score_vencedor = scores[np.arange(len(scores)), np.argmax(scores, axis=1)]

    metricas = calcular_metricas_classificacao(y_oos, pred, list(CLASSES_ALVO))
    log.info("Avaliacao OOS (VAL+TEST, dado nunca usado no treino): %s", metricas)

    previsoes = pd.DataFrame({
        "numero": populacao_oos["numero"].to_numpy(),
        "data_abertura": populacao_oos["data_abertura"].to_numpy(),
        "prioridade_real": y_oos.to_numpy(),
        "prioridade_prevista": pred,
        "score_vencedor": score_vencedor,
    })
    log.info("classes do modelo (ordem de decision_function): %s", list(classes))
    return previsoes, metricas


def gerar_previsoes_prioridade() -> tuple[pd.DataFrame, dict]:
    carregado = load_model(NOME_MODELO)
    populacao, populacao_oos = montar_populacao_oos()

    features_completo = preparar_features_prioridade(populacao)
    validar_features(carregado.metadata, list(features_completo.columns))

    previsoes, metricas_oos = avaliar_oos_e_prever(carregado.modelo, populacao_oos)
    previsoes["modelo_utilizado"] = carregado.metadata["modelo"]
    previsoes["versao_modelo"] = carregado.metadata["versao"]

    log.info(
        "Previsoes de prioridade geradas: %d linha(s) (populacao completa=%d, TRAIN excluido)",
        len(previsoes), len(populacao),
    )
    return previsoes, metricas_oos


def main() -> None:
    from src.load.load_previsoes import load_previsoes_prioridade

    previsoes, metricas_oos = gerar_previsoes_prioridade()
    n = load_previsoes_prioridade(previsoes)
    log.info(
        "gold.previsoes_prioridade atualizada: %d linha(s) upsertadas. Avaliacao OOS: %s",
        n, metricas_oos,
    )


if __name__ == "__main__":
    main()
