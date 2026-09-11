"""Testes de integracao da camada Bronze."""

from src.validation.checks import check_bronze_count
from tests.conftest import TOTAL_ORIGEM


def test_bronze_conta_bate_com_a_origem():
    ok, msg = check_bronze_count()
    assert ok, msg


def test_bronze_tem_o_total_do_arquivo(scalar):
    assert scalar("SELECT COUNT(*) FROM bronze.incidentes_raw") == TOTAL_ORIGEM


def test_bronze_carga_timestamp_sem_nulo(scalar):
    assert scalar(
        "SELECT COUNT(*) FROM bronze.incidentes_raw WHERE carga_timestamp IS NULL"
    ) == 0
