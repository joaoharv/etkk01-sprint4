"""Load Silver: full load de ``silver.incidentes_tratados``."""

from __future__ import annotations

import pandas as pd

from config.logging import get_logger
from src.db import truncate_insert
from src.transform.clean_incidentes import COLUNAS_SILVER

log = get_logger(__name__)


def load_silver(df: pd.DataFrame) -> int:
    """Carrega o DataFrame tratado na Silver. Retorna o numero de linhas carregadas."""
    faltando = set(COLUNAS_SILVER) - set(df.columns)
    if faltando:
        raise ValueError(f"DataFrame nao tem as colunas esperadas da Silver: {sorted(faltando)}")
    return truncate_insert("incidentes_tratados", df[COLUNAS_SILVER], "silver")
