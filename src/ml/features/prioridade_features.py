"""Feature engineering do modelo de classificacao de Prioridade (notebook 02,
Plano 2.1 - Etapa 11).

Populacao e split replicados EXATAMENTE do notebook (celulas 25/29, saida real
de execucao -- nao supostos): incidentes com Prioridade em {2-Alta, 3-Media,
4-Baixa}, Aberto em [2025-09-01, 2026-01-01). Split temporal por mes: TRAIN =
set+out/2025, VAL = nov/2025, TEST = dez/2025.

Features do pipeline VENCEDOR (E03, "Texto + Produto"): so `descricao_resumida`
(TF-IDF, dentro do pipeline persistido) e `produto_prep` (OneHotEncoder, nulo
-> "Desconhecido"). `item_configuracao`, `aberto_por` e features temporais
foram testados pelo notebook (E04-E07) e PIORAM a generalizacao para
descricoes novas -- nao sao reproduzidos aqui (nao e' esquecimento).

Nota sobre nulidade de Produto: a Silver ja substitui nulo por "Não informado"
(regra de qualidade da propria Silver, anterior a este projeto de ML) -- o
notebook usa "Desconhecido" para o mesmo caso, lendo direto do Excel bruto.
Sao rotulos diferentes para o EXATO MESMO conjunto de linhas (confirmado:
82,2% de nulidade no recorte, identico ao que o notebook reporta) -- o
OneHotEncoder e' treinado do zero aqui, entao o rotulo escolhido nao afeta o
resultado numerico do modelo, so o nome da categoria "desconhecida".
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

from config.logging import get_logger
from src.db import get_engine

log = get_logger(__name__)

# Populacao replicada do notebook (celula 25, saida real: "93.403 registros").
CLASSES_ALVO = ("2 - Alta", "3 - Média", "4 - Baixa")
CORTE_REGIME_INICIO = "2025-09-01"
CORTE_FIM = "2026-01-01"

# Split temporal (celula 29, saida real: TRAIN 44.570 | VAL 21.522 | TEST 27.311).
MESES_TRAIN = ("2025-09", "2025-10")
MES_VAL = "2025-11"
MES_TEST = "2025-12"

# Features do pipeline vencedor (E03) -- ver docstring do modulo.
# NUNCA adicionar duracao_segundos/duracao_dias/duracao_outlier_flag (ou
# qualquer classificacao derivada de duracao) aqui: sao pos-desfecho, so
# existem depois de Resolvido/Encerrado, que nao estao disponiveis no momento
# em que a Prioridade precisa ser prevista -- leakage direto (ver auditoria de
# outliers de duracao, docs/PLANO_TRATAMENTO_OUTLIERS_DURACAO.md).
FEATURES_PRIORIDADE = ["descricao_resumida", "produto_prep"]

_PRODUTO_DESCONHECIDO = "Desconhecido"


def carregar_populacao_prioridade(engine: Engine | None = None) -> pd.DataFrame:
    """Populacao EXATA do notebook 02: Prioridade nas 3 classes-alvo, Aberto no
    recorte pos-regime (set/2025 a dez/2025). Fonte: silver.incidentes_tratados.
    """
    engine = engine or get_engine()
    classes = ", ".join(f"'{c}'" for c in CLASSES_ALVO)
    sql = f"""
        SELECT numero, aberto, data_abertura, prioridade, produto, descricao_resumida
        FROM silver.incidentes_tratados
        WHERE prioridade IN ({classes})
          AND aberto >= '{CORTE_REGIME_INICIO}'
          AND aberto < '{CORTE_FIM}'
        ORDER BY aberto
    """
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    df["aberto"] = pd.to_datetime(df["aberto"])
    log.info(
        "Populacao de Prioridade carregada: %d registros (%s a %s)",
        len(df), df["aberto"].min(), df["aberto"].max(),
    )
    return df


def preparar_features_prioridade(df: pd.DataFrame) -> pd.DataFrame:
    """Replica preparar_dataframe() do notebook -- so as 2 colunas que o
    pipeline vencedor (E03) usa. Retorna DataFrame com o MESMO indice de df."""
    saida = pd.DataFrame(index=df.index)
    saida["descricao_resumida"] = df["descricao_resumida"].fillna("")
    saida["produto_prep"] = df["produto"].replace("Não informado", _PRODUTO_DESCONHECIDO)
    return saida[FEATURES_PRIORIDADE]


def split_temporal_prioridade(df: pd.DataFrame):
    """TRAIN (set+out/2025) / VAL (nov/2025) / TEST (dez/2025) -- mesmo corte
    do notebook (celula 29). df precisa ter a coluna 'aberto'."""
    mes = df["aberto"].dt.to_period("M").astype(str)
    train = df[mes.isin(MESES_TRAIN)]
    val = df[mes == MES_VAL]
    test = df[mes == MES_TEST]
    return train, val, test
