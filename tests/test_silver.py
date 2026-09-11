"""Testes de integracao da camada Silver."""

from src.validation.checks import (
    check_silver_no_dup,
    check_silver_no_nulls,
    check_silver_vs_bronze,
)


def test_silver_sem_nulos_obrigatorios():
    ok, msg = check_silver_no_nulls()
    assert ok, msg


def test_silver_sem_duplicata_por_numero():
    ok, msg = check_silver_no_dup()
    assert ok, msg


def test_silver_nunca_maior_que_bronze():
    ok, msg = check_silver_vs_bronze()
    assert ok, msg


def test_silver_colunas_de_data_em_tipo_nativo(scalar):
    tipos = {
        "aberto": "timestamp without time zone",
        "data_abertura": "date",
        "duracao_segundos": "bigint",
    }
    for coluna, esperado in tipos.items():
        atual = scalar(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='silver' AND table_name='incidentes_tratados' "
            f"AND column_name='{coluna}'"
        )
        assert atual == esperado, f"{coluna}: {atual} != {esperado}"


def test_silver_preserva_as_5_prioridades(scalar):
    assert scalar(
        "SELECT COUNT(DISTINCT prioridade) FROM silver.incidentes_tratados"
    ) == 5
