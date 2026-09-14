"""Testes de src/ml/alertas_threshold.py (Plano 2.1, Etapa 15).

Contra o banco real (gold.ml_volume_diario, populado desde a Etapa 10) --
sem mocks, mesmo padrao dos demais testes de ML deste projeto.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from src.db import get_engine
from src.ml.alertas_threshold import (
    REGRA_ERRO_D7,
    REGRA_VOLUME,
    calcular_threshold_erro_d7,
    calcular_threshold_volume,
    registrar_thresholds,
)
from src.ml.features.volume_features import DATA_CORTE_REGIME

_REGRA_TESTE = "__teste_threshold__"


@pytest.fixture(autouse=True)
def _limpa_regra_teste():
    yield
    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM gold.alertas_thresholds WHERE regra = :regra"),
            {"regra": _REGRA_TESTE},
        )


def test_threshold_volume_usa_apenas_o_regime_vigente():
    """Regressao direta da divergencia encontrada e corrigida na Etapa 15:
    a formula NAO pode misturar o regime antigo (pre 2025-09) com o vigente."""
    resultado = calcular_threshold_volume()

    assert resultado["regra"] == REGRA_VOLUME
    assert resultado["regime_data_corte"] == DATA_CORTE_REGIME

    with get_engine().connect() as conn:
        media_real, desvio_real = conn.execute(
            text(
                "SELECT avg(volume_total), stddev(volume_total) "
                "FROM gold.ml_volume_diario WHERE data_abertura >= :corte"
            ),
            {"corte": DATA_CORTE_REGIME},
        ).one()

    assert resultado["media"] == pytest.approx(float(media_real), abs=0.1)
    assert resultado["desvio"] == pytest.approx(float(desvio_real), abs=0.1)
    assert resultado["threshold"] == pytest.approx(
        float(media_real) + 2 * float(desvio_real), abs=0.1
    )


def test_threshold_volume_nao_inclui_dias_do_regime_antigo():
    """O regime antigo (media~115) e' bem menor que o vigente (media~765) --
    se a query vazasse dias antigos, a media cairia bem abaixo de 700."""
    resultado = calcular_threshold_volume()
    assert resultado["media"] > 700


def test_threshold_volume_traz_percentis_coerentes():
    resultado = calcular_threshold_volume()
    assert resultado["p90"] <= resultado["p95"] <= resultado["p99"]
    assert resultado["media"] < resultado["p90"]


def test_threshold_erro_d7_e_duas_vezes_o_mae_recebido():
    resultado = calcular_threshold_erro_d7({"MAE": 100.0, "n": 10})
    assert resultado["regra"] == REGRA_ERRO_D7
    assert resultado["threshold"] == 200.0
    assert resultado["qtd_dias_historico"] == 10


def test_threshold_erro_d7_nao_consulta_o_banco(monkeypatch):
    """Deriva so do dict de metricas ja calculado pelo pipeline -- nunca
    recalcula MAE consultando o Postgres de novo."""
    def _explode(*args, **kwargs):
        raise AssertionError("calcular_threshold_erro_d7 nao deveria acessar o banco")

    monkeypatch.setattr("src.ml.alertas_threshold.get_engine", _explode)
    calcular_threshold_erro_d7({"MAE": 50.0, "n": 5})


def test_registrar_thresholds_e_append_only_nunca_sobrescreve():
    linha_1 = {
        "regra": _REGRA_TESTE, "threshold": 100.0, "media": 50.0, "desvio": 10.0,
        "p90": 60.0, "p95": 65.0, "p99": 70.0, "qtd_dias_historico": 30,
        "qtd_dias_acima_historico": 1, "pct_dias_acima_historico": 3.33,
        "regime_data_corte": DATA_CORTE_REGIME, "detalhe": "linha 1",
    }
    linha_2 = {**linha_1, "threshold": 200.0, "detalhe": "linha 2"}

    registrar_thresholds([linha_1])
    registrar_thresholds([linha_2])

    with get_engine().connect() as conn:
        thresholds = conn.execute(
            text(
                "SELECT threshold FROM gold.alertas_thresholds "
                "WHERE regra = :regra ORDER BY calculado_em"
            ),
            {"regra": _REGRA_TESTE},
        ).scalars().all()

    assert [float(t) for t in thresholds] == [100.0, 200.0]
