"""Testes de integracao da camada Gold."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.validation.checks import check_gold_vs_silver


def test_gold_total_bate_com_silver():
    ok, msg = check_gold_vs_silver()
    assert ok, msg


def test_gold_tem_as_13_tabelas(scalar):
    """12 tabelas originais + gold.previsoes_prioridade (Plano 2.1, Etapa 5).

    Conta so BASE TABLE -- information_schema.tables tambem lista VIEWs (ex.:
    gold.ml_volume_diario, Etapa 10), que tem checagem propria abaixo. Contar
    os dois juntos deixaria este numero subindo silenciosamente a cada view
    nova, sem dizer o que realmente mudou."""
    assert scalar(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema='gold' AND table_type='BASE TABLE'"
    ) == 13


def test_gold_tem_a_view_ml_volume_diario(scalar):
    """View auxiliar do Dashboard 06 (Plano 2.1, Etapa 10) -- populacao exata
    do modelo de volume (2025+, sem as classes raras de prioridade), nunca a
    populacao de BI de gold.incidentes_diario_total."""
    tipo = scalar(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema='gold' AND table_name='ml_volume_diario'"
    )
    assert tipo == "VIEW"


def test_build_gold_nunca_inclui_previsoes(scalar):
    """Regressao direta do bug encontrado na Etapa 8: build_gold() incluia um
    stub sempre-vazio de 'previsoes', e load_gold() TRUNCATE qualquer
    DataFrame vazio -- isso apagava gold.previsoes a cada execucao do ETL
    principal, destruindo o trabalho do pipeline de ML (src/ml/predict_volume.py).
    gold.previsoes e gold.previsoes_prioridade sao propriedade exclusiva do
    pipeline de ML: build_gold() nunca pode conhece-las."""
    from src.db import read_table
    from src.transform.aggregate_gold import build_gold

    silver = read_table("incidentes_tratados", "silver")
    tabelas = build_gold(silver)

    assert "previsoes" not in tabelas
    assert "previsoes_prioridade" not in tabelas


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


# --- gold.previsoes: contrato do Plano 2.1 (Etapa 5) -----------------------------

_INSERT_PREVISAO = (
    "INSERT INTO gold.previsoes "
    "(data_referencia, serie, horizonte, valor_previsto, modelo_utilizado, versao_modelo) "
    "VALUES ('2025-06-10', :serie, :horizonte, :valor, 'teste', 'v1')"
)


def test_gold_previsoes_data_alvo_d1_e_d7(engine):
    """data_alvo e' SEMPRE data_referencia + 1 (D+1) ou + 7 (D+7), gerada pelo Postgres --
    nunca calculada em Python (Plano 2.1)."""
    with engine.begin() as conn:
        d1 = conn.execute(
            text(_INSERT_PREVISAO + " RETURNING data_alvo"),
            {"serie": "__teste_data_alvo__", "horizonte": "D+1", "valor": 10},
        ).scalar()
        d7 = conn.execute(
            text(_INSERT_PREVISAO + " RETURNING data_alvo"),
            {"serie": "__teste_data_alvo__", "horizonte": "D+7", "valor": 10},
        ).scalar()
        # limpeza dentro da mesma transacao -- nao deixa residuo em gold.previsoes
        conn.execute(
            text("DELETE FROM gold.previsoes WHERE serie = '__teste_data_alvo__'")
        )

    assert str(d1) == "2025-06-11"
    assert str(d7) == "2025-06-17"


def test_gold_previsoes_rejeita_horizonte_invalido(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(_INSERT_PREVISAO),
                {"serie": "__teste__", "horizonte": "D+99", "valor": 10},
            )


def test_gold_previsoes_rejeita_valor_negativo(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(_INSERT_PREVISAO),
                {"serie": "__teste__", "horizonte": "D+1", "valor": -5},
            )


def test_gold_previsoes_populada_pelo_pipeline_com_os_dois_horizontes(scalar):
    """Desde a Etapa 8, gold.previsoes e' alimentada por src/ml/predict_volume.py
    (Model Registry) -- deixou de ser 'sempre vazia' (essa era a regra ate a
    Etapa 7). Confere que os dois horizontes existem e que nenhuma linha ficou
    com modelo/versao em branco (rastreabilidade obrigatoria)."""
    horizontes = scalar(
        "SELECT COUNT(DISTINCT horizonte) FROM gold.previsoes"
    )
    assert horizontes == 2

    sem_rastreabilidade = scalar(
        "SELECT COUNT(*) FROM gold.previsoes "
        "WHERE modelo_utilizado IS NULL OR versao_modelo IS NULL"
    )
    assert sem_rastreabilidade == 0

    d1_e_persistencia = scalar(
        "SELECT COUNT(*) FROM gold.previsoes "
        "WHERE horizonte = 'D+1' AND modelo_utilizado != 'persistencia'"
    )
    assert d1_e_persistencia == 0, "D+1 nunca pode ser atribuida a um modelo ML"


# --- gold.previsoes_prioridade: contrato do Plano 2.1 (Etapa 5) ------------------

_INSERT_PREVISAO_PRIORIDADE = (
    "INSERT INTO gold.previsoes_prioridade "
    "(numero, data_abertura, prioridade_prevista, modelo_utilizado, versao_modelo) "
    "VALUES (:numero, '2025-06-10', :prioridade, 'teste', 'v1')"
)


def test_gold_previsoes_prioridade_schema(scalar):
    colunas_esperadas = {
        "numero", "data_abertura", "prioridade_real", "prioridade_prevista",
        "score_vencedor", "modelo_utilizado", "versao_modelo", "gerado_em",
    }
    colunas = scalar(
        "SELECT string_agg(column_name, ',') FROM information_schema.columns "
        "WHERE table_schema='gold' AND table_name='previsoes_prioridade'"
    )
    assert set(colunas.split(",")) == colunas_esperadas


def test_gold_previsoes_prioridade_rejeita_classe_invalida(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(_INSERT_PREVISAO_PRIORIDADE),
                {"numero": "__teste__", "prioridade": "9 - Invalida"},
            )


def test_gold_previsoes_prioridade_populada_pelo_pipeline(scalar):
    """Desde a Etapa 11, gold.previsoes_prioridade e' alimentada por
    src/ml/predict_prioridade.py -- deixou de ser 'sempre vazia' (essa era a
    regra ate a Etapa 10, mesma transicao que gold.previsoes teve na Etapa 8)."""
    total = scalar("SELECT COUNT(*) FROM gold.previsoes_prioridade")
    assert total > 0

    sem_rastreabilidade = scalar(
        "SELECT COUNT(*) FROM gold.previsoes_prioridade "
        "WHERE modelo_utilizado IS NULL OR versao_modelo IS NULL"
    )
    assert sem_rastreabilidade == 0

    sem_real = scalar(
        "SELECT COUNT(*) FROM gold.previsoes_prioridade WHERE prioridade_real IS NULL"
    )
    assert sem_real == 0, "populacao e' estatica -- prioridade_real sempre conhecida"
