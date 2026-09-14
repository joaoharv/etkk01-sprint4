"""Testes de src/ml/features/prioridade_features.py (Plano 2.1, Etapa 11).

Numeros de populacao/split conferidos contra a saida REAL de execucao do
notebook 02 (celulas 25/29) -- nao valores supostos.
"""

from __future__ import annotations

import pandas as pd

from src.ml.features.prioridade_features import (
    CLASSES_ALVO,
    FEATURES_PRIORIDADE,
    carregar_populacao_prioridade,
    preparar_features_prioridade,
    split_temporal_prioridade,
)


_COLUNAS_DURACAO_PROIBIDAS = {
    "duracao_segundos", "duracao_dias", "duracao_horas", "duracao_outlier_flag",
    "duracao_faixa_percentil", "duracao_classificacao", "duracao_valida",
}


def test_features_prioridade_nao_inclui_colunas_de_duracao():
    """Nenhuma coluna de duracao (oficial ou derivada da auditoria de outliers)
    pode entrar como feature: Duracao so existe apos Resolvido/Encerrado, que
    nao estao disponiveis no momento em que a Prioridade e' prevista -- leakage
    direto (docs/PLANO_TRATAMENTO_OUTLIERS_DURACAO.md)."""
    assert _COLUNAS_DURACAO_PROIBIDAS.isdisjoint(FEATURES_PRIORIDADE)


def test_populacao_prioridade_nao_seleciona_colunas_de_duracao():
    """A query de populacao (carregar_populacao_prioridade) nao pode nem
    selecionar duracao do banco -- reforco de que a barreira e' estrutural,
    nao apenas uma lista de features."""
    populacao = carregar_populacao_prioridade()
    assert _COLUNAS_DURACAO_PROIBIDAS.isdisjoint(populacao.columns)


def test_populacao_reproduz_o_notebook():
    """Notebook (celula 25, saida real): 93.403 registros."""
    populacao = carregar_populacao_prioridade()
    assert len(populacao) == 93403
    assert set(populacao["prioridade"].unique()) == set(CLASSES_ALVO)
    assert populacao["aberto"].min() >= pd.Timestamp("2025-09-01")
    assert populacao["aberto"].max() < pd.Timestamp("2026-01-01")


def test_split_reproduz_o_notebook():
    """Notebook (celula 29, saida real): TRAIN 44.570 | VAL 21.522 | TEST 27.311."""
    populacao = carregar_populacao_prioridade()
    train, val, test = split_temporal_prioridade(populacao)

    assert len(train) == 44570
    assert len(val) == 21522
    assert len(test) == 27311
    assert len(train) + len(val) + len(test) == len(populacao)


def test_split_e_cronologico_sem_sobreposicao():
    populacao = carregar_populacao_prioridade()
    train, val, test = split_temporal_prioridade(populacao)

    assert train["aberto"].max() < val["aberto"].min()
    assert val["aberto"].max() < test["aberto"].min()
    assert set(train.index).isdisjoint(val.index)
    assert set(val.index).isdisjoint(test.index)
    assert set(train.index).isdisjoint(test.index)


def test_preparar_features_produz_exatamente_as_colunas_do_pipeline_vencedor():
    populacao = carregar_populacao_prioridade()
    features = preparar_features_prioridade(populacao)

    assert list(features.columns) == FEATURES_PRIORIDADE
    assert not features["descricao_resumida"].isna().any(), "fillna('') tem que remover todo NaN"
    assert not features["produto_prep"].isna().any()
    assert "Não informado" not in features["produto_prep"].unique(), (
        "produto_prep usa o rotulo 'Desconhecido', nunca o rotulo interno da Silver"
    )


def test_preparar_features_nao_inclui_colunas_de_leakage():
    """Nenhuma das colunas de leakage do notebook (Categoria, Status, KPI,
    Duracao, Resolvido, Encerrado, Codigo de fechamento, Solucao, Incidente
    Pai) pode aparecer na matriz de features -- so descricao_resumida e
    produto_prep existem por design (ver FEATURES_PRIORIDADE)."""
    assert FEATURES_PRIORIDADE == ["descricao_resumida", "produto_prep"]
