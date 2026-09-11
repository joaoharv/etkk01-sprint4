"""Fixtures dos testes de integracao.

Os testes rodam contra o banco real (sem mocks) e assumem que a DAG
``pipeline_incidentes_ti`` ja executou ao menos uma vez.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from src.db import get_engine

# Total de linhas do arquivo LW-DATASET.xlsx fornecido.
TOTAL_ORIGEM = 122543


@pytest.fixture(scope="session")
def engine():
    return get_engine()


@pytest.fixture(scope="session")
def scalar(engine) -> Callable[[str], object]:
    def _scalar(sql: str):
        with engine.connect() as conn:
            return conn.exec_driver_sql(sql).scalar()

    return _scalar
