"""Load Bronze: full load de ``bronze.incidentes_raw`` via COPY.

TRUNCATE + COPY na mesma transacao — reexecutar nao duplica. A coluna
``carga_timestamp`` e preenchida pelo DEFAULT now() da tabela (nao entra no COPY).
"""

from __future__ import annotations

import io

import pandas as pd

from config.logging import get_logger
from src.db import get_engine
from src.extract.read_source import COLUNAS_ORIGEM

log = get_logger(__name__)

_TABELA = "bronze.incidentes_raw"
_COLUNAS = list(COLUNAS_ORIGEM.values())  # as 19 colunas de negocio, na ordem da Bronze


def load_bronze(df: pd.DataFrame) -> int:
    """Carrega o DataFrame bruto na Bronze. Retorna o numero de linhas carregadas."""
    faltando = set(_COLUNAS) - set(df.columns)
    if faltando:
        raise ValueError(f"DataFrame nao tem as colunas esperadas da Bronze: {sorted(faltando)}")

    buffer = io.StringIO()
    df[_COLUNAS].to_csv(buffer, index=False, na_rep="")
    buffer.seek(0)

    colunas_sql = ", ".join(_COLUNAS)
    copy_sql = (
        f"COPY {_TABELA} ({colunas_sql}) "
        "FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
    )

    conn = get_engine().raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"TRUNCATE TABLE {_TABELA}")
        cursor.copy_expert(copy_sql, buffer)
        linhas = cursor.rowcount if cursor.rowcount != -1 else len(df)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    log.info("Bronze carregada: %d linhas", linhas)
    return linhas
