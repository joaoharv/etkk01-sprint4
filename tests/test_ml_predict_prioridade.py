"""Testes de src/ml/predict_prioridade.py (Plano 2.1, Etapa 11).

Contra o banco real e o artefato real do Model Registry (models/prioridade/,
gerado nesta mesma etapa) -- sem mocks.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ml.features.prioridade_features import (
    CLASSES_ALVO,
    carregar_populacao_prioridade,
    split_temporal_prioridade,
)
from src.ml.model_registry import load_model
from src.ml.predict_prioridade import (
    avaliar_oos_e_prever,
    gerar_previsoes_prioridade,
    montar_populacao_oos,
)


def test_populacao_oos_e_exatamente_val_mais_test():
    populacao = carregar_populacao_prioridade()
    train, val, test = split_temporal_prioridade(populacao)

    _pop, oos = montar_populacao_oos()

    assert set(oos.index) == set(val.index) | set(test.index)
    assert set(oos.index).isdisjoint(train.index)
    assert len(oos) == len(val) + len(test) == 21522 + 27311


def test_avaliacao_e_previsoes_usam_exatamente_a_mesma_fatia():
    """Prova por construcao: previsoes e metrica vem da mesma chamada a
    .predict()/.decision_function() (mesmo padrao do modelo de volume)."""
    carregado = load_model("prioridade")
    _pop, oos = montar_populacao_oos()

    previsoes, metricas = avaliar_oos_e_prever(carregado.modelo, oos)

    assert len(previsoes) == len(oos) == metricas["n"]
    assert set(previsoes["numero"]) == set(oos["numero"])


def test_score_vencedor_e_o_maior_score_de_decision_function():
    carregado = load_model("prioridade")
    _pop, oos = montar_populacao_oos()
    previsoes, _ = avaliar_oos_e_prever(carregado.modelo, oos.head(50))

    from src.ml.features.prioridade_features import preparar_features_prioridade
    X = preparar_features_prioridade(oos.head(50))
    scores = carregado.modelo.decision_function(X)

    for i in range(len(previsoes)):
        assert previsoes["score_vencedor"].iloc[i] == pytest.approx(scores[i].max())


def test_gerar_previsoes_prioridade_schema_pronto_para_o_loader():
    previsoes, metricas_oos = gerar_previsoes_prioridade()

    colunas_esperadas = {
        "numero", "data_abertura", "prioridade_real", "prioridade_prevista",
        "score_vencedor", "modelo_utilizado", "versao_modelo",
    }
    assert colunas_esperadas.issubset(set(previsoes.columns))
    assert set(previsoes["prioridade_prevista"].unique()).issubset(set(CLASSES_ALVO))
    assert set(previsoes["prioridade_real"].unique()).issubset(set(CLASSES_ALVO))
    assert not previsoes[list(colunas_esperadas)].isna().any().any()
    assert previsoes["modelo_utilizado"].unique().tolist() == ["linearsvc_prioridade"]
    assert metricas_oos["n"] == len(previsoes) == 48833


def test_previsoes_nao_incluem_nenhum_numero_do_periodo_de_treino():
    populacao = carregar_populacao_prioridade()
    train, _val, _test = split_temporal_prioridade(populacao)
    numeros_treino = set(train["numero"])

    previsoes, _ = gerar_previsoes_prioridade()
    assert numeros_treino.isdisjoint(set(previsoes["numero"]))
