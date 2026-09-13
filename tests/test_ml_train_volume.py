"""Testes de src/ml/train_volume.py (Plano 2.1, Etapa 7).

treinar() e' testado contra o banco real -- reproduz o split, o alpha e as
metricas do notebook 01 (celulas 75 e 86, saida REAL de execucao), sem
re-otimizar nada (alpha e' fixo). Nao chama salvar_artefato() aqui: gerar o
artefato de producao em models/volume_d7/ e' um passo manual (`python -m
src.ml.train_volume`), nao responsabilidade dos testes.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ml.train_volume import ALPHA_D7, split_estrategia_ii, montar_dataset, treinar

# Numeros REPORTADOS pela execucao real do notebook (celulas 75/86) -- usados
# aqui so como alvo de reproducao, nunca re-derivados ou re-otimizados.
NOTEBOOK_VAL_MAE = 105.154
NOTEBOOK_TEST_MAE = 144.507
NOTEBOOK_TEST_N = 24


def test_alpha_nao_foi_re_otimizado_nesta_etapa():
    """Valor fixo, igual ao reportado pelo notebook -- nao uma busca nova."""
    assert ALPHA_D7 == 0.001


def test_split_estrategia_ii_produz_os_mesmos_recortes_de_data_do_notebook():
    dataset = montar_dataset()
    tr, va, te = split_estrategia_ii(dataset)

    assert tr.index.max() < pd.Timestamp("2025-11-01")
    assert va.index.min() >= pd.Timestamp("2025-11-01")
    assert va.index.max() < pd.Timestamp("2025-12-01")
    assert te.index.min() >= pd.Timestamp("2025-12-01")

    # TEST tem 24 dias, nao 31: os ultimos 7 dias de dezembro nao tem target_d7
    # (precisariam de dado em jan/2026, que nao existe na base). Mesmo n do
    # notebook (celula 86, saida real: "n=24.000").
    assert len(te) == NOTEBOOK_TEST_N


def test_dataset_comeca_em_29_01_apos_o_corte_de_warmup():
    dataset = montar_dataset()
    assert dataset.index.min() == pd.Timestamp("2025-01-29")


def test_treinar_reproduz_as_metricas_reportadas_pelo_notebook():
    """Fidelidade de reproducao, nao otimizacao: Ridge(alpha=0.001) treinado so
    em TRAIN tem que bater (tolerancia de arredondamento) com o VAL_MAE e o
    TEST_MAE que o notebook reportou de verdade (celulas 75 e 86)."""
    resultado = treinar()

    assert resultado["metricas_val"]["MAE"] == pytest.approx(NOTEBOOK_VAL_MAE, abs=1.0)
    assert resultado["metricas_test"]["MAE"] == pytest.approx(NOTEBOOK_TEST_MAE, abs=1.0)
    assert resultado["metricas_test"]["n"] == NOTEBOOK_TEST_N


def test_modelo_de_producao_foi_treinado_em_train_mais_val():
    """O artefato persistido usa TRAIN+VAL (Secao 21 do notebook) -- nao so TRAIN."""
    resultado = treinar()
    periodo = resultado["periodo_treino_producao"]

    assert periodo["inicio"] == "2025-01-29"
    assert periodo["fim"] == "2025-11-30"  # inclui novembro (VAL)


def test_metricas_test_nunca_usam_dado_de_train():
    """Guarda-corpo direto contra a regra do Plano 2.1: a metrica de TEST vem
    de um fit que so viu TRAIN -- confere que TEST e TRAIN nao se sobrepoem
    no tempo em nenhum cenario desta etapa."""
    dataset = montar_dataset()
    tr, _va, te = split_estrategia_ii(dataset)
    assert tr.index.max() < te.index.min()
