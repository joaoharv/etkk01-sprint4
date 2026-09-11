"""Validacao de qualidade entre camadas.

Cada checagem devolve ``(ok: bool, mensagem: str)`` e so faz SELECT (nunca grava).
``validate_pipeline()`` roda todas e levanta ``RuntimeError`` se alguma falhar —
e o gate da DAG (task ``validate_pipeline``).
"""

from __future__ import annotations

from config.logging import get_logger
from src.db import get_engine
from src.extract.read_source import read_source

log = get_logger(__name__)

Checagem = tuple[bool, str]


def _scalar(sql: str) -> int:
    with get_engine().connect() as conn:
        return conn.exec_driver_sql(sql).scalar()


def check_bronze_count() -> Checagem:
    """Bronze tem exatamente o total de linhas do arquivo de origem."""
    origem = len(read_source())
    bronze = _scalar("SELECT COUNT(*) FROM bronze.incidentes_raw")
    return origem == bronze, f"origem={origem} | bronze={bronze}"


def check_silver_no_nulls() -> Checagem:
    """Colunas obrigatorias da Silver sem NULL."""
    n = _scalar(
        """
        SELECT COUNT(*) FROM silver.incidentes_tratados
        WHERE prioridade IS NULL OR produto IS NULL
           OR categoria IS NULL OR subcategoria IS NULL
        """
    )
    return n == 0, f"linhas com nulo obrigatorio: {n}"


def check_silver_no_dup() -> Checagem:
    """Sem 'numero' duplicado na Silver."""
    n = _scalar(
        """
        SELECT COUNT(*) FROM (
            SELECT numero FROM silver.incidentes_tratados
            GROUP BY numero HAVING COUNT(*) > 1
        ) d
        """
    )
    return n == 0, f"numeros duplicados: {n}"


def check_silver_vs_bronze() -> Checagem:
    """Silver nunca tem mais linhas que a Bronze."""
    silver = _scalar("SELECT COUNT(*) FROM silver.incidentes_tratados")
    bronze = _scalar("SELECT COUNT(*) FROM bronze.incidentes_raw")
    return silver <= bronze, f"silver={silver} | bronze={bronze}"


def check_gold_vs_silver() -> Checagem:
    """A soma de gold.incidentes_diario_total bate com a contagem da Silver."""
    gold = _scalar(
        "SELECT COALESCE(SUM(total_incidentes), 0) FROM gold.incidentes_diario_total"
    )
    silver = _scalar("SELECT COUNT(*) FROM silver.incidentes_tratados")
    return gold == silver, f"gold_total={gold} | silver={silver}"


def check_previsoes_vazia() -> Checagem:
    """gold.previsoes esta vazia (ML fora do escopo desta entrega)."""
    n = _scalar("SELECT COUNT(*) FROM gold.previsoes")
    return n == 0, f"gold.previsoes: {n} linhas (esperado 0)"


CHECAGENS = (
    check_bronze_count,
    check_silver_no_nulls,
    check_silver_no_dup,
    check_silver_vs_bronze,
    check_gold_vs_silver,
    check_previsoes_vazia,
)


def validate_pipeline() -> None:
    """Roda todas as checagens; levanta RuntimeError com a lista de falhas."""
    falhas: list[str] = []
    for fn in CHECAGENS:
        ok, msg = fn()
        marca = "OK" if ok else "FALHOU"
        (log.info if ok else log.error)("[%s] %s | %s", marca, fn.__name__, msg)
        if not ok:
            falhas.append(f"{fn.__name__}: {msg}")

    if falhas:
        raise RuntimeError(
            "Validacao do pipeline falhou:\n  - " + "\n  - ".join(falhas)
        )
    log.info("Validacao do pipeline: %d checagens OK", len(CHECAGENS))
