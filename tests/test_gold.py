"""Testes de integracao da camada Gold."""

import pytest

from src.validation.checks import check_gold_vs_silver, check_previsoes_vazia


def test_gold_total_bate_com_silver():
    ok, msg = check_gold_vs_silver()
    assert ok, msg


def test_gold_previsoes_esta_vazia():
    ok, msg = check_previsoes_vazia()
    assert ok, msg


def test_gold_tem_as_12_tabelas(scalar):
    assert scalar(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='gold'"
    ) == 12


@pytest.mark.parametrize(
    "tabela",
    [
        "incidentes_diario_prioridade",
        "incidentes_diario_grupo",
        "incidentes_diario_status",
        "incidentes_diario_kpi",
        "incidentes_horario",
    ],
)
def test_gold_dimensao_soma_o_total_da_silver(scalar, tabela):
    silver = scalar("SELECT COUNT(*) FROM silver.incidentes_tratados")
    soma = scalar(f"SELECT SUM(total_incidentes) FROM gold.{tabela}")
    assert soma == silver, f"{tabela}: soma={soma} != silver={silver}"
