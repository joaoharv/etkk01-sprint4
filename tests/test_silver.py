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


def test_silver_descricao_resumida_existe_e_e_nullable(scalar):
    """Coluna existe como text nullable, sem DEFAULT (Plano 2.1, Etapa 4)."""
    tipo = scalar(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema='silver' AND table_name='incidentes_tratados' "
        "AND column_name='descricao_resumida'"
    )
    assert tipo == "text"

    nulavel = scalar(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema='silver' AND table_name='incidentes_tratados' "
        "AND column_name='descricao_resumida'"
    )
    assert nulavel == "YES"

    default = scalar(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_schema='silver' AND table_name='incidentes_tratados' "
        "AND column_name='descricao_resumida'"
    )
    assert default is None


def test_silver_descricao_resumida_e_passthrough_sem_fillna(scalar):
    """Nao pode ter sido preenchida com 'Não informado' nem string vazia --
    esse tratamento pertence ao feature engineering do ML (Etapa 11), nunca a Silver."""
    suspeitos = scalar(
        "SELECT COUNT(*) FROM silver.incidentes_tratados "
        "WHERE descricao_resumida IN ('', 'Não informado')"
    )
    assert suspeitos == 0


def test_silver_descricao_resumida_bate_com_bronze(scalar):
    """Contagem de nao-nulos identica a bronze.incidentes_raw -- prova de passthrough."""
    bronze = scalar("SELECT COUNT(descricao_resumida) FROM bronze.incidentes_raw")
    silver = scalar("SELECT COUNT(descricao_resumida) FROM silver.incidentes_tratados")
    assert silver == bronze, f"silver={silver} != bronze={bronze}"
