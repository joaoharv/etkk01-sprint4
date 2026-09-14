"""Testes de src/ml/features/volume_features.py (Plano 2.1, Etapa 6).

build_features_volume/construir_targets sao testados com serie sintetica (sem
banco, deterministica: volume(dia i) = i, para tornar qualquer lag trivial de
conferir manualmente). carregar_volume_diario e' testado contra o banco real
(fixture `engine` de tests/conftest.py), reproduzindo a populacao exata do
notebook 01 (2025+, sem as classes raras de prioridade).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ml.features.volume_features import (
    DATA_CORTE_REGIME,
    FEATURES_D7,
    LAGS,
    build_features_volume,
    carregar_volume_diario,
    construir_targets,
)


def _serie_sintetica(n_dias=40, inicio="2025-01-01"):
    """Serie diaria onde o valor do dia i e' sempre i (0, 1, 2, ...) -- torna a
    reconstrucao manual de qualquer lag/target trivial de conferir."""
    idx = pd.date_range(inicio, periods=n_dias, freq="D")
    return pd.Series(range(n_dias), index=idx, dtype="float64", name="volume_total")


_COLUNAS_DURACAO_PROIBIDAS = {
    "duracao_segundos", "duracao_dias", "duracao_horas", "duracao_outlier_flag",
    "duracao_faixa_percentil", "duracao_classificacao", "duracao_valida",
}


def test_features_volume_nao_inclui_colunas_de_duracao():
    """Nenhuma coluna de duracao (oficial ou derivada da auditoria de outliers)
    pode entrar como feature do modelo de volume D+7 (docs/PLANO_TRATAMENTO_OUTLIERS_DURACAO.md)."""
    assert _COLUNAS_DURACAO_PROIBIDAS.isdisjoint(FEATURES_D7)


# --- build_features_volume: warmup, leakage, colunas -----------------------------

def test_build_features_descarta_exatamente_os_28_dias_de_warmup():
    serie = _serie_sintetica(n_dias=40)
    features = build_features_volume(serie)

    assert len(features) == 40 - 28
    assert features.index.min() == serie.index[28]
    assert features.index.max() == serie.index[-1]


def test_build_features_nenhum_nan_apos_o_corte_de_warmup():
    serie = _serie_sintetica(n_dias=40)
    features = build_features_volume(serie)
    assert not features.isna().any().any()


@pytest.mark.parametrize("k", LAGS)
def test_build_features_lag_k_reconstruido_manualmente_sem_leakage(k):
    """Para cada lag_k, o valor na linha t tem que ser EXATAMENTE volume_total(t-k)
    -- nunca volume_total(t) ou qualquer valor >= t. Mesmo espirito da auditoria de
    leakage do notebook (Secao 12/19): reconstrucao manual, nao so alegacao."""
    serie = _serie_sintetica(n_dias=40)
    features = build_features_volume(serie)

    for data_t, valor_lag in features[f"lag_{k}"].items():
        esperado = serie.loc[data_t - pd.Timedelta(days=k)]
        assert valor_lag == esperado, f"lag_{k} em {data_t.date()}: {valor_lag} != {esperado}"


def test_build_features_periodo_pos_set_2025_antes_e_depois_do_corte():
    # 60 dias a partir de 01/08 -> apos descartar os 28 de warmup, a serie de
    # features vai de 29/08 a 29/09: cobre os dois lados do corte (01/09).
    serie = _serie_sintetica(n_dias=60, inicio="2025-08-01")
    features = build_features_volume(serie)
    corte = pd.Timestamp(DATA_CORTE_REGIME)

    antes = features.loc[features.index < corte, "periodo_pos_set_2025"]
    depois = features.loc[features.index >= corte, "periodo_pos_set_2025"]

    assert len(antes) > 0 and len(depois) > 0, "cenario de teste precisa cobrir os dois lados do corte"
    assert (antes == 0).all()
    assert (depois == 1).all()


def test_build_features_colunas_sao_exatamente_features_d7():
    serie = _serie_sintetica(n_dias=40)
    features = build_features_volume(serie)
    assert list(features.columns) == FEATURES_D7


# --- construir_targets: shift correto, NaN so no fim -----------------------------

def test_construir_targets_d1_e_d7_deslocados_corretamente():
    serie = _serie_sintetica(n_dias=20)
    targets = construir_targets(serie)

    for data_t in serie.index[:-1]:
        assert targets.loc[data_t, "target_d1"] == serie.loc[data_t + pd.Timedelta(days=1)]

    for data_t in serie.index[:-7]:
        assert targets.loc[data_t, "target_d7"] == serie.loc[data_t + pd.Timedelta(days=7)]


def test_construir_targets_nan_apenas_no_fim_da_serie():
    serie = _serie_sintetica(n_dias=20)
    targets = construir_targets(serie)

    assert targets["target_d1"].isna().sum() == 1
    assert targets["target_d1"].iloc[:-1].notna().all()

    assert targets["target_d7"].isna().sum() == 7
    assert targets["target_d7"].iloc[:-7].notna().all()


# --- integracao com o banco real: populacao exata do notebook --------------------

def test_carregar_volume_diario_reproduz_a_populacao_do_notebook(engine):
    """2025+, excluindo 1-Critica/5-Muito Baixa -- numeros conferidos manualmente
    no banco antes desta implementacao (ver relatorio da Etapa 6): 365 dias,
    soma=121485, sem buracos mesmo apos excluir as classes raras."""
    serie = carregar_volume_diario(engine)

    assert len(serie) == 365
    assert serie.index.min() == pd.Timestamp("2025-01-01")
    assert serie.index.max() == pd.Timestamp("2025-12-31")
    assert int(serie.sum()) == 121485
    assert not serie.isna().any()


def test_build_features_end_to_end_com_dado_real(engine):
    serie = carregar_volume_diario(engine)
    features = build_features_volume(serie)

    assert len(features) == 365 - 28
    assert not features.isna().any().any()
    assert list(features.columns) == FEATURES_D7


def test_targets_end_to_end_com_dado_real_sem_vazamento_de_futuro(engine):
    """target_d7 conferido contra o proprio valor real 7 dias a frente -- nao
    confia so na funcao sendo testada."""
    serie = carregar_volume_diario(engine)
    targets = construir_targets(serie)

    data_referencia = pd.Timestamp("2025-06-01")
    data_alvo = data_referencia + pd.Timedelta(days=7)
    assert targets.loc[data_referencia, "target_d7"] == serie.loc[data_alvo]
