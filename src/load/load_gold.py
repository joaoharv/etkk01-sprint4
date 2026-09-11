"""Load Gold: full load de cada tabela gold.*."""

from __future__ import annotations

import pandas as pd

from config.logging import get_logger
from src.db import get_engine, truncate_insert

log = get_logger(__name__)


def load_gold(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Carrega cada DataFrame na tabela gold.<chave>. Retorna {tabela: linhas}."""
    resultado: dict[str, int] = {}
    for nome, df in tables.items():
        if df.empty:
            # Tabela reservada (previsoes): so garante o estado vazio.
            with get_engine().begin() as conn:
                conn.exec_driver_sql(f'TRUNCATE TABLE "gold"."{nome}"')
            resultado[nome] = 0
            log.info("gold.%s: 0 linhas (tabela vazia)", nome)
        else:
            resultado[nome] = truncate_insert(nome, df, "gold")
    return resultado
