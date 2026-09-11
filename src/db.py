"""Acesso ao PostgreSQL para a camada ETL.

Toda a configuracao vem de variaveis de ambiente (DEC4) — nenhuma credencial no
codigo. Dentro dos containers o docker-compose injeta as variaveis; fora deles,
o arquivo ``.env`` da raiz e carregado como fallback (sem sobrescrever o que ja
estiver no ambiente).

    POSTGRES_HOST      default: "postgres"  (nome do servico na rede Docker;
                                             use "localhost" para rodar do host)
    POSTGRES_PORT      default: "5432"
    POSTGRES_DB        default: "incidentes_ti"
    POSTGRES_USER      obrigatoria
    POSTGRES_PASSWORD  obrigatoria
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config.logging import get_logger

log = get_logger(__name__)

try:  # fallback opcional para execucao fora dos containers
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # python-dotenv nao instalado (ok dentro do container)
    pass


def _require(nome: str) -> str:
    valor = os.environ.get(nome)
    if not valor:
        raise RuntimeError(
            f"Variavel de ambiente {nome} nao definida. "
            "Configure o .env (veja .env.example) ou rode dentro do container."
        )
    return valor


def _database_url() -> str:
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB", "incidentes_ti")
    user = _require("POSTGRES_USER")
    password = _require("POSTGRES_PASSWORD")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Engine SQLAlchemy unica para o processo (pool padrao, pre_ping ligado)."""
    url = _database_url()
    log.info("Conectando ao Postgres em %s", url.split("@", 1)[-1])
    return create_engine(url, pool_pre_ping=True, future=True)


def run_sql_file(path: str | Path) -> None:
    """Executa um arquivo .sql inteiro em uma unica transacao.

    Usado pela task ``create_schema`` para aplicar os scripts de DDL idempotentes.
    """
    caminho = Path(path)
    if not caminho.is_file():
        raise FileNotFoundError(f"Script SQL nao encontrado: {caminho}")

    sql = caminho.read_text(encoding="utf-8")
    with get_engine().begin() as conn:
        conn.exec_driver_sql(sql)
    log.info("SQL aplicado: %s", caminho.name)


def read_table(table: str, schema: str) -> pd.DataFrame:
    """Le uma tabela inteira para um DataFrame. Usado pelas tasks silver/gold e testes."""
    with get_engine().connect() as conn:
        return pd.read_sql_table(table, conn, schema=schema)


def truncate_insert(table: str, df: pd.DataFrame, schema: str) -> int:
    """Full load: TRUNCATE seguido de INSERT, na mesma transacao.

    Retorna o numero de linhas inseridas. Reexecutar nao duplica dados.
    O chunksize e ajustado ao numero de colunas para nao estourar o limite de
    65535 parametros por statement do Postgres (method="multi").
    """
    chunksize = max(1, 60000 // max(1, len(df.columns)))
    with get_engine().begin() as conn:
        conn.exec_driver_sql(f'TRUNCATE TABLE "{schema}"."{table}"')
        df.to_sql(
            table,
            conn,
            schema=schema,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=chunksize,
        )
    log.info("%s.%s: %d linhas carregadas (full load)", schema, table, len(df))
    return len(df)
