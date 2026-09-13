"""Testes de src/load/load_previsoes.py (Plano 2.1, Etapas 8 e 11).

Usa uma 'serie'/'numero' sentinela para nunca colidir com previsoes reais, e
limpa explicitamente ao final de cada teste -- mesmo padrao ja usado em
tests/test_gold.py (Etapa 5) para gold.previsoes/gold.previsoes_prioridade.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.db import get_engine
from src.load.load_previsoes import load_previsoes_prioridade, load_previsoes_volume

_SERIE_TESTE = "__teste_upsert__"
_NUMERO_TESTE = "__teste_upsert__"


@pytest.fixture(autouse=True)
def _limpa_serie_teste():
    yield
    with get_engine().begin() as conn:
        conn.exec_driver_sql(
            f"DELETE FROM gold.previsoes WHERE serie = '{_SERIE_TESTE}'"
        )
        conn.exec_driver_sql(
            f"DELETE FROM gold.previsoes_prioridade WHERE numero = '{_NUMERO_TESTE}'"
        )


def _df(valor: float, modelo: str = "teste", versao: str = "v1") -> pd.DataFrame:
    return pd.DataFrame([{
        "data_referencia": pd.Timestamp("2025-06-10"),
        "serie": _SERIE_TESTE,
        "horizonte": "D+7",
        "valor_previsto": valor,
        "modelo_utilizado": modelo,
        "versao_modelo": versao,
    }])


def _conta_linhas_teste() -> int:
    with get_engine().connect() as conn:
        return conn.exec_driver_sql(
            f"SELECT COUNT(*) FROM gold.previsoes WHERE serie = '{_SERIE_TESTE}'"
        ).scalar()


def test_load_previsoes_dataframe_vazio_nao_grava_nada():
    n = load_previsoes_volume(pd.DataFrame(columns=[
        "data_referencia", "serie", "horizonte", "valor_previsto",
        "modelo_utilizado", "versao_modelo",
    ]))
    assert n == 0
    assert _conta_linhas_teste() == 0


def test_load_previsoes_upsert_nao_duplica_ao_rodar_duas_vezes():
    load_previsoes_volume(_df(420))
    load_previsoes_volume(_df(420))
    assert _conta_linhas_teste() == 1


def test_load_previsoes_upsert_atualiza_o_valor_sem_criar_linha_nova():
    load_previsoes_volume(_df(420, modelo="ridge_d7", versao="v1"))
    load_previsoes_volume(_df(395, modelo="ridge_d7", versao="v2"))

    assert _conta_linhas_teste() == 1
    with get_engine().connect() as conn:
        linha = conn.exec_driver_sql(
            f"SELECT valor_previsto, versao_modelo FROM gold.previsoes "
            f"WHERE serie = '{_SERIE_TESTE}'"
        ).one()
    assert float(linha.valor_previsto) == 395
    assert linha.versao_modelo == "v2"


def test_load_previsoes_data_alvo_gerada_automaticamente():
    load_previsoes_volume(_df(100))
    with get_engine().connect() as conn:
        data_alvo = conn.exec_driver_sql(
            f"SELECT data_alvo FROM gold.previsoes WHERE serie = '{_SERIE_TESTE}'"
        ).scalar()
    assert str(data_alvo) == "2025-06-17"  # data_referencia (10/06) + 7 (D+7)


# --- load_previsoes_prioridade (Etapa 11) ----------------------------------

def _df_prioridade(prevista: str = "3 - Média", score: float = 1.5, versao: str = "v1") -> pd.DataFrame:
    return pd.DataFrame([{
        "numero": _NUMERO_TESTE,
        "data_abertura": pd.Timestamp("2025-06-10").date(),
        "prioridade_real": "3 - Média",
        "prioridade_prevista": prevista,
        "score_vencedor": score,
        "modelo_utilizado": "teste",
        "versao_modelo": versao,
    }])


def _conta_linhas_teste_prioridade() -> int:
    with get_engine().connect() as conn:
        return conn.exec_driver_sql(
            f"SELECT COUNT(*) FROM gold.previsoes_prioridade WHERE numero = '{_NUMERO_TESTE}'"
        ).scalar()


def test_load_previsoes_prioridade_dataframe_vazio_nao_grava_nada():
    n = load_previsoes_prioridade(pd.DataFrame(columns=[
        "numero", "data_abertura", "prioridade_real", "prioridade_prevista",
        "score_vencedor", "modelo_utilizado", "versao_modelo",
    ]))
    assert n == 0
    assert _conta_linhas_teste_prioridade() == 0


def test_load_previsoes_prioridade_upsert_nao_duplica():
    load_previsoes_prioridade(_df_prioridade())
    load_previsoes_prioridade(_df_prioridade())
    assert _conta_linhas_teste_prioridade() == 1


def test_load_previsoes_prioridade_upsert_atualiza_sem_duplicar():
    load_previsoes_prioridade(_df_prioridade(prevista="4 - Baixa", score=1.0, versao="v1"))
    load_previsoes_prioridade(_df_prioridade(prevista="2 - Alta", score=2.0, versao="v2"))

    assert _conta_linhas_teste_prioridade() == 1
    with get_engine().connect() as conn:
        linha = conn.exec_driver_sql(
            f"SELECT prioridade_prevista, versao_modelo FROM gold.previsoes_prioridade "
            f"WHERE numero = '{_NUMERO_TESTE}'"
        ).one()
    assert linha.prioridade_prevista == "2 - Alta"
    assert linha.versao_modelo == "v2"
