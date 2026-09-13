"""Inferencia do modelo de volume (Plano 2.1, Etapa 8).

Tres conceitos, DELIBERADAMENTE distintos -- nunca confundir um com o outro:

- ``montar_dataset_oos()`` / ``avaliar_oos_e_backfill_d7()``: a fatia de dados
  com ``data_referencia`` FORA do periodo usado para treinar o artefato
  persistido (``>= FIM_VAL`` de ``train_volume.py`` -- o modelo de producao foi
  treinado em TRAIN+VAL, entao so o que vem depois de VAL e' genuinamente
  "nunca visto"). E' a UNICA fatia da qual se pode tirar uma metrica
  (MAE/RMSE/sMAPE/R2) e chama-la de "desempenho do modelo".
- O **backfill** (as previsoes linha a linha, para ``gold.previsoes``) usa
  EXATAMENTE essa mesma fatia -- nunca o periodo de treino. Isso e' proposital:
  qualquer coisa em ``gold.previsoes`` e', por construcao, genuinamente fora
  do treino, entao nunca pode ser mal-interpretada como uma curva otimista/
  in-sample no Grafana. (Se um dia for necessario visualizar tambem o periodo
  de treino, isso exige uma coluna nova marcando o escopo -- fora do escopo
  desta etapa, ver relatorio.)
- ``gerar_forward_d7()`` / ``gerar_d1()`` (forward): 1 previsao para o dia
  seguinte ao ultimo dia disponivel na base -- data-alvo ainda nao existe,
  sem valor real para comparar (``LEFT JOIN`` no Grafana mostraria "aguardando
  real", nao um erro).

D+1 e' persistencia pura (Secao 16 do notebook: nenhum modelo bateu isso) --
sem parametro treinado, sem nocao de treino/OOS. Ainda assim e' gerada na
MESMA janela de datas do D+7 (backfill+forward), para o Dashboard comparar os
dois horizontes lado a lado.

Roda como script manual (mesma maturidade de train_volume.py -- ainda NAO e'
uma task de DAG, isso e' a Etapa 9):

    docker compose exec airflow-webserver python -m src.ml.predict_volume
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.logging import get_logger
from src.ml.features.volume_features import FEATURES_D7, build_features_volume, carregar_volume_diario
from src.ml.metrics import calcular_metricas
from src.ml.model_registry import load_model, validar_features
from src.ml.train_volume import NOME_MODELO, split_estrategia_ii, montar_dataset

log = get_logger(__name__)

SERIE = "total"
HORIZONTE_D1 = "D+1"
HORIZONTE_D7 = "D+7"
MODELO_D1 = "persistencia"
VERSAO_D1 = "1.0"


def montar_dataset_oos() -> pd.DataFrame:
    """Linhas com ``data_referencia`` fora do periodo de treino do artefato
    persistido (``>= FIM_VAL``) -- a UNICA fatia legitima para metricas.

    Reaproveita ``train_volume.montar_dataset()``/``split_estrategia_ii()`` de proposito:
    o corte de OOS tem que vir da MESMA fonte de verdade do corte de treino,
    nunca de uma constante duplicada que poderia divergir em silencio.
    """
    dataset = montar_dataset()
    _tr, _va, te = split_estrategia_ii(dataset)
    return te


def avaliar_oos_e_backfill_d7(modelo, oos: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Uma unica previsao sobre ``oos`` alimenta as duas coisas -- garante,
    por construcao (nao por coincidencia), que backfill e avaliacao usam
    exatamente a mesma fatia de dados."""
    pred = np.clip(modelo.predict(oos[FEATURES_D7]), 0, None)

    metricas = calcular_metricas(oos["target_d7"], pred)
    log.info("Avaliacao OOS (D+7, dado nunca usado no treino do artefato persistido): %s", metricas)

    backfill = pd.DataFrame({
        "data_referencia": oos.index,
        "serie": SERIE,
        "horizonte": HORIZONTE_D7,
        "valor_previsto": pred,
    })
    return backfill, metricas


def gerar_forward_d7(modelo, features_completo: pd.DataFrame) -> pd.DataFrame:
    """1 previsao para o ultimo dia disponivel na base -> data_alvo (Etapa 5,
    coluna gerada) ainda nao existe -- sem valor real para comparar."""
    ultimo_dia = features_completo.index.max()
    x = features_completo.loc[[ultimo_dia], FEATURES_D7]
    pred = float(np.clip(modelo.predict(x), 0, None)[0])

    return pd.DataFrame({
        "data_referencia": [ultimo_dia],
        "serie": [SERIE],
        "horizonte": [HORIZONTE_D7],
        "valor_previsto": [pred],
    })


def gerar_d1(volume_diario: pd.Series, datas_referencia: pd.Index) -> pd.DataFrame:
    """Persistencia pura: ``valor_previsto(t) = volume_total(t)`` -- sem
    modelo, sem treino, sem nocao de OOS (Secao 16 do notebook). Escorada na
    mesma janela de datas do D+7 (backfill + forward) por simplicidade e para
    o Dashboard comparar os dois horizontes lado a lado -- nao ha nenhum
    motivo metodologico para restringir D+1 a essa janela (persistencia nao
    tem risco de leakage/overlap com nada), so uma escolha de escopo desta
    etapa."""
    valores = volume_diario.loc[datas_referencia]
    return pd.DataFrame({
        "data_referencia": datas_referencia,
        "serie": SERIE,
        "horizonte": HORIZONTE_D1,
        "valor_previsto": valores.to_numpy(),
    })


def gerar_previsoes_volume() -> tuple[pd.DataFrame, dict]:
    """Orquestra os tres modos e devolve o DataFrame pronto para o loader
    (Etapa 8) + as metricas de avaliacao OOS (log/monitoramento -- nunca
    gravadas em gold.previsoes, que nao tem coluna de metrica)."""
    carregado = load_model(NOME_MODELO)
    volume_diario = carregar_volume_diario()
    features_completo = build_features_volume(volume_diario)
    validar_features(carregado.metadata, list(features_completo.columns))

    oos = montar_dataset_oos()
    backfill_d7, metricas_oos = avaliar_oos_e_backfill_d7(carregado.modelo, oos)
    forward_d7 = gerar_forward_d7(carregado.modelo, features_completo)

    d7 = pd.concat([backfill_d7, forward_d7], ignore_index=True)
    d7["modelo_utilizado"] = carregado.metadata["modelo"]
    d7["versao_modelo"] = carregado.metadata["versao"]

    datas_d1 = pd.Index(pd.concat([backfill_d7["data_referencia"], forward_d7["data_referencia"]]))
    d1 = gerar_d1(volume_diario, datas_d1)
    d1["modelo_utilizado"] = MODELO_D1
    d1["versao_modelo"] = VERSAO_D1

    previsoes = pd.concat([d1, d7], ignore_index=True)
    log.info(
        "Previsoes de volume geradas: %d linha(s) (D+1=%d, D+7=%d, 1 forward em cada horizonte)",
        len(previsoes), len(d1), len(d7),
    )
    return previsoes, metricas_oos


def main() -> None:
    from src.load.load_previsoes import load_previsoes_volume

    previsoes, metricas_oos = gerar_previsoes_volume()
    n = load_previsoes_volume(previsoes)
    log.info("gold.previsoes atualizada: %d linha(s) upsertadas. Avaliacao OOS (D+7): %s", n, metricas_oos)


if __name__ == "__main__":
    main()
