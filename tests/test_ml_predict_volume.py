"""Testes de src/ml/predict_volume.py (Plano 2.1, Etapa 8).

Contra o banco real e o artefato real do Model Registry (models/volume_d7/,
gerado na Etapa 7) -- sem mocks, mesmo padrao do resto do projeto.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ml.features.volume_features import build_features_volume, carregar_volume_diario
from src.ml.model_registry import load_model
from src.ml.predict_volume import (
    HORIZONTE_D1,
    HORIZONTE_D7,
    MODELO_D1,
    SERIE,
    VERSAO_D1,
    avaliar_oos_e_backfill_d7,
    gerar_d1,
    gerar_forward_d7,
    gerar_previsoes_volume,
    montar_dataset_oos,
)


def test_backfill_e_avaliacao_usam_exatamente_a_mesma_fatia_de_dados():
    """Prova por construcao (nao por coincidencia de datas): as previsoes do
    backfill e a metrica de avaliacao vem da MESMA chamada de predict()."""
    carregado = load_model("volume_d7")
    oos = montar_dataset_oos()

    backfill, metricas = avaliar_oos_e_backfill_d7(carregado.modelo, oos)

    assert set(backfill["data_referencia"]) == set(oos.index)
    assert metricas["n"] == len(oos) == len(backfill)


def test_forward_d7_preve_para_o_dia_seguinte_ao_ultimo_disponivel():
    carregado = load_model("volume_d7")
    volume_diario = carregar_volume_diario()
    features = build_features_volume(volume_diario)

    forward = gerar_forward_d7(carregado.modelo, features)

    assert len(forward) == 1
    assert forward["data_referencia"].iloc[0] == pd.Timestamp("2025-12-31")
    assert forward["horizonte"].iloc[0] == HORIZONTE_D7
    assert forward["valor_previsto"].iloc[0] >= 0


def test_d1_e_persistencia_pura_identica_ao_volume_do_proprio_dia():
    """D+1 nao usa modelo nenhum -- valor_previsto(t) tem que ser EXATAMENTE
    volume_total(t), nunca uma aproximacao."""
    volume_diario = carregar_volume_diario()
    datas = volume_diario.index[-10:]

    d1 = gerar_d1(volume_diario, datas)

    for _, linha in d1.iterrows():
        assert linha["valor_previsto"] == volume_diario.loc[linha["data_referencia"]]
        assert linha["horizonte"] == HORIZONTE_D1


def test_gerar_previsoes_volume_schema_pronto_para_o_loader():
    previsoes, metricas_oos = gerar_previsoes_volume()

    colunas_esperadas = {
        "data_referencia", "serie", "horizonte",
        "valor_previsto", "modelo_utilizado", "versao_modelo",
    }
    assert colunas_esperadas.issubset(set(previsoes.columns))

    assert set(previsoes["horizonte"].unique()) == {HORIZONTE_D1, HORIZONTE_D7}
    assert set(previsoes["serie"].unique()) == {SERIE}
    assert (previsoes["valor_previsto"] >= 0).all(), "CHECK (valor_previsto >= 0) rejeitaria isso"
    assert not previsoes.isna().any().any()

    d1_modelos = previsoes.loc[previsoes["horizonte"] == HORIZONTE_D1, "modelo_utilizado"].unique()
    assert list(d1_modelos) == [MODELO_D1], "D+1 tem que ser rotulada como persistencia, nunca como modelo ML"

    d1_versoes = previsoes.loc[previsoes["horizonte"] == HORIZONTE_D1, "versao_modelo"].unique()
    assert list(d1_versoes) == [VERSAO_D1]

    assert "metricas_oos" not in previsoes.columns  # metrica nao e' previsao -- fica so no dict de retorno
    assert metricas_oos["n"] > 0


def test_previsoes_nao_incluem_nenhuma_data_do_periodo_de_treino_do_artefato():
    """Regressao direta do teste obrigatorio (test_forecast_evaluation_no_train_overlap)
    olhando para o resultado final que vai para o loader, nao so para o dataset
    intermediario."""
    from src.ml.train_volume import montar_dataset, split_estrategia_ii

    dataset = montar_dataset()
    tr, va, _te = split_estrategia_ii(dataset)
    periodo_treino = set(tr.index) | set(va.index)

    previsoes, _ = gerar_previsoes_volume()
    datas_d7_backfill = set(
        pd.to_datetime(previsoes.loc[previsoes["horizonte"] == HORIZONTE_D7, "data_referencia"])
    ) - {pd.Timestamp("2025-12-31")}  # exclui a linha forward, que naturalmente nao esta no dataset de treino

    assert periodo_treino.isdisjoint(datas_d7_backfill)
