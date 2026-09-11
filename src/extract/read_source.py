"""Extract: leitura do LW-DATASET.xlsx.

Funcao pura — le o Excel, valida o conjunto de colunas e devolve um DataFrame
com os nomes ja em snake_case. NAO converte tipos (tudo string), NAO filtra
linhas, NAO remove nulos. Toda decisao de negocio fica na Silver.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from config.logging import get_logger

log = get_logger(__name__)

# Mapa explicito nome-na-origem -> nome canonico. Fonte da verdade dos nomes de
# coluna para todo o pipeline. Duas renomeacoes nao sao mera normalizacao:
#   "Duração"          -> "duracao_segundos"  (a unidade e segundos)
#   "Entrou para KPI?" -> "entrou_kpi"        (encurtado, alinhado a Bronze)
COLUNAS_ORIGEM: dict[str, str] = {
    "Número": "numero",
    "Prioridade": "prioridade",
    "Produto": "produto",
    "Categoria": "categoria",
    "Subcategoria": "subcategoria",
    "Grupo designado": "grupo_designado",
    "Item de configuração": "item_configuracao",
    "Aberto": "aberto",
    "Resolvido": "resolvido",
    "Encerrado": "encerrado",
    "Duração": "duracao_segundos",
    "Código de fechamento": "codigo_fechamento",
    "Descrição resumida": "descricao_resumida",
    "Solução": "solucao",
    "Aberto por": "aberto_por",
    "Incidente Pai": "incidente_pai",
    "Status": "status",
    "Entrou para KPI?": "entrou_kpi",
    "KPI Violado?": "kpi_violado",
}


def _caminho_padrao() -> Path:
    """Caminho da fonte: SOURCE_FILE_PATH (definido no compose) ou data/ do repo."""
    env = os.environ.get("SOURCE_FILE_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "LW-DATASET.xlsx"


def read_source(path: str | Path | None = None) -> pd.DataFrame:
    """Le a planilha de origem e devolve o DataFrame bruto com colunas snake_case.

    Levanta ``FileNotFoundError`` se o arquivo nao existir e ``ValueError`` se o
    conjunto de colunas divergir do esperado.
    """
    caminho = Path(path) if path is not None else _caminho_padrao()
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Arquivo de origem nao encontrado: {caminho}. "
            "Confirme que data/LW-DATASET.xlsx esta no repositorio e montado no container."
        )

    df = pd.read_excel(caminho, sheet_name=0, dtype=str)

    faltando = sorted(set(COLUNAS_ORIGEM) - set(df.columns))
    inesperadas = sorted(set(df.columns) - set(COLUNAS_ORIGEM))
    if faltando or inesperadas:
        raise ValueError(
            "Colunas da origem divergem do esperado. "
            f"Faltando: {faltando}. Inesperadas: {inesperadas}."
        )

    df = df.rename(columns=COLUNAS_ORIGEM)[list(COLUNAS_ORIGEM.values())]
    log.info(
        "Origem lida: %d linhas, %d colunas (%s)", len(df), df.shape[1], caminho.name
    )
    return df
