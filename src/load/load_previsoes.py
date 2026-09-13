"""Loaders de gold.previsoes / gold.previsoes_prioridade -- UPSERT transacional
(Plano 2.1, Etapas 8 e 11).

As duas tabelas representam a previsao VIGENTE por chave -- ao contrario do
padrao truncate+insert usado no resto do projeto (bronze/silver/gold
dimensional), NUNCA sao truncadas: reprocessar sobrescreve o valor da mesma
chave, mas nunca apaga previsoes de outras linhas (decisao registrada no
Plano 2.1 -- ver models/README.md, sql/create/04_gold_core.sql e
sql/create/06_gold_ml.sql).

``data_alvo`` (gold.previsoes) e' coluna GERADA pelo Postgres (Etapa 5) --
nunca aparece no INSERT/UPDATE aqui.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Column, Date, DateTime, MetaData, Numeric, Table, Text, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.logging import get_logger
from src.db import get_engine

log = get_logger(__name__)

_COLUNAS_VOLUME = [
    "data_referencia", "serie", "horizonte",
    "valor_previsto", "modelo_utilizado", "versao_modelo",
]

_COLUNAS_PRIORIDADE = [
    "numero", "data_abertura", "prioridade_real", "prioridade_prevista",
    "score_vencedor", "modelo_utilizado", "versao_modelo",
]

_METADATA = MetaData()

_TABELA_PREVISOES = Table(
    "previsoes",
    _METADATA,
    Column("data_referencia", Date),
    Column("serie", Text),
    Column("horizonte", Text),
    Column("valor_previsto", Numeric),
    Column("modelo_utilizado", Text),
    Column("versao_modelo", Text),
    Column("gerado_em", DateTime),
    schema="gold",
)

_TABELA_PREVISOES_PRIORIDADE = Table(
    "previsoes_prioridade",
    _METADATA,
    Column("numero", Text),
    Column("data_abertura", Date),
    Column("prioridade_real", Text),
    Column("prioridade_prevista", Text),
    Column("score_vencedor", Numeric),
    Column("modelo_utilizado", Text),
    Column("versao_modelo", Text),
    Column("gerado_em", DateTime),
    schema="gold",
)


def load_previsoes_volume(df: pd.DataFrame) -> int:
    """UPSERT por (data_referencia, serie, horizonte), em UMA transacao --
    uma falha no meio do lote nao deixa previsoes parciais gravadas."""
    if df.empty:
        log.info("load_previsoes_volume: nada para carregar (DataFrame vazio)")
        return 0

    registros = df[_COLUNAS_VOLUME].to_dict(orient="records")

    stmt = pg_insert(_TABELA_PREVISOES).values(registros)
    stmt = stmt.on_conflict_do_update(
        index_elements=["data_referencia", "serie", "horizonte"],
        set_={
            "valor_previsto": stmt.excluded.valor_previsto,
            "modelo_utilizado": stmt.excluded.modelo_utilizado,
            "versao_modelo": stmt.excluded.versao_modelo,
            "gerado_em": func.now(),
        },
    )

    with get_engine().begin() as conn:
        conn.execute(stmt)

    log.info("gold.previsoes: %d linha(s) upsertada(s)", len(registros))
    return len(registros)


def load_previsoes_prioridade(df: pd.DataFrame) -> int:
    """UPSERT por numero (PK), em UMA transacao -- mesmo padrao de
    load_previsoes_volume, chave diferente (grao = incidente, nao dia)."""
    if df.empty:
        log.info("load_previsoes_prioridade: nada para carregar (DataFrame vazio)")
        return 0

    registros = df[_COLUNAS_PRIORIDADE].to_dict(orient="records")

    stmt = pg_insert(_TABELA_PREVISOES_PRIORIDADE).values(registros)
    stmt = stmt.on_conflict_do_update(
        index_elements=["numero"],
        set_={
            "data_abertura": stmt.excluded.data_abertura,
            "prioridade_real": stmt.excluded.prioridade_real,
            "prioridade_prevista": stmt.excluded.prioridade_prevista,
            "score_vencedor": stmt.excluded.score_vencedor,
            "modelo_utilizado": stmt.excluded.modelo_utilizado,
            "versao_modelo": stmt.excluded.versao_modelo,
            "gerado_em": func.now(),
        },
    )

    with get_engine().begin() as conn:
        conn.execute(stmt)

    log.info("gold.previsoes_prioridade: %d linha(s) upsertada(s)", len(registros))
    return len(registros)
