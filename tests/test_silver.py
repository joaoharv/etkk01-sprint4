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


# --- duracao_dias / duracao_outlier_flag (auditoria de outliers de duracao) ------
# Ver docs/PLANO_TRATAMENTO_OUTLIERS_DURACAO.md e
# docs/REVISAO_PLANO_TRATAMENTO_OUTLIERS_DURACAO.md.


def test_silver_duracao_segundos_nunca_negativa(scalar):
    """duracao_segundos original permanece intocado -- esta e' so uma protecao
    de regressao (nenhum caso na fonte atual)."""
    assert scalar(
        "SELECT COUNT(*) FROM silver.incidentes_tratados WHERE duracao_segundos < 0"
    ) == 0


def test_silver_duracao_dias_e_derivada_sem_arredondar(scalar):
    """duracao_dias = duracao_segundos / 86400.0 em TODA linha, sem excecao --
    tolerancia so para erro de ponto flutuante (numeric vs double precision)."""
    divergentes = scalar(
        "SELECT COUNT(*) FROM silver.incidentes_tratados "
        "WHERE abs(duracao_dias - (duracao_segundos / 86400.0)) > 1e-9"
    )
    assert divergentes == 0


def test_silver_duracao_outlier_flag_bate_com_p99(scalar):
    """duracao_outlier_flag = (duracao_segundos > P99 do lote inteiro), P99
    calculado dinamicamente -- nunca um numero fixo. Recalcula o P99 direto no
    banco e confere que a flag bate exatamente com esse limite recem-calculado."""
    p99 = scalar(
        "SELECT percentile_cont(0.99) WITHIN GROUP (ORDER BY duracao_segundos) "
        "FROM silver.incidentes_tratados"
    )
    divergentes = scalar(
        "SELECT COUNT(*) FROM silver.incidentes_tratados "
        f"WHERE duracao_outlier_flag != (duracao_segundos > {p99})"
    )
    assert divergentes == 0


def test_silver_duracao_valida_e_outlier_flag_sao_conceitos_independentes(scalar):
    """duracao_valida (sanidade estrutural) e duracao_outlier_flag (estatistico)
    nao podem ser a mesma coisa: deve existir pelo menos um registro onde as
    duas sao True ao mesmo tempo (outlier estatistico que e' estruturalmente
    valido -- o caso normal e esperado para a cauda longa de duracao)."""
    ambas_true = scalar(
        "SELECT COUNT(*) FROM silver.incidentes_tratados "
        "WHERE duracao_valida AND duracao_outlier_flag"
    )
    assert ambas_true > 0, (
        "Se nenhum registro tem as duas flags True ao mesmo tempo, "
        "duracao_outlier_flag pode estar sendo confundida com duracao_valida."
    )
