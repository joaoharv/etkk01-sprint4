"""Testes de gold.ml_volume_diario (Plano 2.1, Etapa 10).

A view existe so para o Dashboard 06 poder comparar "real x previsto" na
MESMA populacao que o modelo usa (Etapa 6: 2025+, sem as classes raras de
prioridade) -- nunca a populacao de BI de gold.incidentes_diario_total. Este
teste garante que a view em SQL nunca diverge de carregar_volume_diario() em
Python -- as duas tem que expressar exatamente a mesma regra de negocio.
"""

from __future__ import annotations

import pandas as pd

from src.ml.features.volume_features import carregar_volume_diario


def test_view_gold_ml_volume_diario_bate_com_carregar_volume_diario(scalar, engine):
    """Compara linha a linha (nao so soma/contagem) -- prova mais forte do
    que so bater agregados que poderiam coincidir por acaso."""
    serie_python = carregar_volume_diario()

    df_view = pd.read_sql(
        "SELECT data_abertura, volume_total FROM gold.ml_volume_diario ORDER BY data_abertura",
        engine,
    )
    serie_view = df_view.set_index(pd.to_datetime(df_view["data_abertura"]))["volume_total"]
    serie_view.index.name = "data_abertura"

    pd.testing.assert_series_equal(
        serie_python.sort_index(),
        serie_view.sort_index(),
        check_names=False,
        check_dtype=False,
        check_freq=False,
    )


def test_view_gold_ml_volume_diario_nao_usa_a_populacao_de_bi(scalar):
    """Confirma que a view NAO e' so um alias de gold.incidentes_diario_total
    -- tem que excluir as classes raras (soma menor)."""
    soma_view = scalar(
        "SELECT SUM(volume_total) FROM gold.ml_volume_diario"
    )
    soma_bi = scalar(
        "SELECT SUM(total_incidentes) FROM gold.incidentes_diario_total "
        "WHERE data_abertura >= '2025-01-01'"
    )
    assert soma_view < soma_bi
    assert soma_view == 121485
