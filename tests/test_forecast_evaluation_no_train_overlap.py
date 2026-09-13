"""Teste OBRIGATORIO do Plano 2.1 (Etapa 8).

Garante que a avaliacao OOS do modelo de volume nunca usa nenhuma observacao
que tambem pertence ao periodo de treino do artefato PERSISTIDO (TRAIN+VAL,
Secao 21 do notebook / src/ml/train_volume.py). Comparacao por CONJUNTO DE
DATAS real (nao so por limite de data) -- a forma mais forte de provar
ausencia de sobreposicao, nao so alegar.
"""

from __future__ import annotations

from src.ml.predict_volume import montar_dataset_oos
from src.ml.train_volume import montar_dataset, split_estrategia_ii


def test_avaliacao_oos_nao_sobrepoe_periodo_de_treino_do_artefato_persistido():
    dataset = montar_dataset()
    tr, va, _te = split_estrategia_ii(dataset)

    # TRAIN+VAL: exatamente o que o Ridge persistido (modelo de producao,
    # Etapa 7) usou para se ajustar -- nunca pode aparecer na avaliacao.
    periodo_treino_do_artefato = set(tr.index) | set(va.index)

    oos = montar_dataset_oos()
    periodo_avaliacao = set(oos.index)

    assert len(periodo_avaliacao) > 0, "cenario vazio nao prova nada"
    assert periodo_treino_do_artefato.isdisjoint(periodo_avaliacao), (
        "A avaliacao OOS usou pelo menos uma data que tambem esta no periodo "
        "de treino do modelo persistido -- isso invalidaria a metrica "
        "reportada como desempenho do modelo."
    )


def test_periodo_de_avaliacao_e_exatamente_o_periodo_de_test():
    """A fatia OOS usada pela inferencia tem que ser exatamente TEST (>= FIM_VAL)
    -- nem um dia a mais (contaminaria com TRAIN/VAL), nem a menos."""
    dataset = montar_dataset()
    _tr, _va, te = split_estrategia_ii(dataset)

    oos = montar_dataset_oos()

    assert set(oos.index) == set(te.index)
