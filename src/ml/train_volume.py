"""Treino do modelo de volume D+7 (Ridge) -- Plano 2.1, Etapa 7.

Reproduz FIELMENTE o modelo do notebook 01 (Secoes 15, 16, 18 e 21): mesmas
features (Etapa 6), mesmo split (Estrategia II), mesmo alpha. O alpha (0.001)
e' o valor JA REPORTADO pela execucao real do notebook (celula 75: "D+7:
melhor alpha Ridge = 0.001") -- nao e' re-otimizado nem re-derivado por um
grid search novo nesta etapa, por instrucao explicita: qualquer melhoria ou
tuning fica para uma etapa futura, separada e autorizada.

Dois fits, papel diferente cada um -- mesma distincao do notebook:
  - modelo de AVALIACAO: treinado so em TRAIN (jan-out/2025), nunca viu
    VAL/TEST. As metricas gravadas em metadata.json vem DESTE fit (e' a
    unica forma honesta de reportar MAE/RMSE -- nunca com dado de TRAIN).
  - modelo de PRODUCAO: retreinado em TRAIN+VAL (jan-nov/2025, Secao 21 do
    notebook). E' o artefato persistido em model.pkl -- TEST continua de
    fora do ajuste dos dois.

Roda SEMPRE dentro do container Airflow (nunca no host) -- garante que o
scikit-learn/numpy que serializam o .pkl sao os mesmos da inferencia. NAO e'
task de DAG -- e' um script manual:

    docker compose exec airflow-webserver python -m src.ml.train_volume
"""

from __future__ import annotations

import json
import platform
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge

from config.logging import get_logger
from src.ml.features.volume_features import (
    FEATURES_D7,
    build_features_volume,
    carregar_volume_diario,
    construir_targets,
)
from src.ml.metrics import calcular_metricas

log = get_logger(__name__)

# Hiperparametro EXATO reportado pela execucao real do notebook (celula 75).
# NAO re-otimizado nesta etapa -- ver docstring do modulo.
ALPHA_D7 = 0.001
RANDOM_STATE = 42

# Split "Estrategia II" (notebook, Secao 10) -- mesmos cortes de data. Reutilizado
# por src/ml/predict_volume.py (Etapa 8) para derivar o corte de avaliacao OOS a
# partir da MESMA fonte de verdade do split de treino -- nunca duplicado.
FIM_TRAIN = "2025-11-01"  # TRAIN: < FIM_TRAIN
FIM_VAL = "2025-12-01"    # VAL: [FIM_TRAIN, FIM_VAL); TEST: >= FIM_VAL

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
NOME_MODELO = "volume_d7"
VERSAO = "v1"


def split_estrategia_ii(frame: pd.DataFrame):
    tr = frame[frame.index < FIM_TRAIN]
    va = frame[(frame.index >= FIM_TRAIN) & (frame.index < FIM_VAL)]
    te = frame[frame.index >= FIM_VAL]
    return tr, va, te


def montar_dataset() -> pd.DataFrame:
    """Features (Etapa 6) + target_d7, restrito as linhas onde o target existe.

    365 dias -> build_features_volume() ja descarta os 28 de warmup (337) ->
    dropna(target_d7) descarta mais 7 no fim (330: 2025-01-29 a 2025-12-24).
    """
    volume = carregar_volume_diario()
    features = build_features_volume(volume)
    targets = construir_targets(volume)
    dataset = features.join(targets[["target_d7"]], how="inner")
    return dataset.dropna(subset=["target_d7"])


def treinar() -> dict:
    """Executa o treino/avaliacao completos. Nao grava nada em disco -- ver
    ``salvar_artefato()``. Devolve o modelo de producao + as metricas de
    avaliacao (TRAIN-only fit) + o periodo usado no treino de producao."""
    dataset = montar_dataset()
    tr, va, te = split_estrategia_ii(dataset)

    log.info(
        "Split Estrategia II: TRAIN %d (%s a %s) | VAL %d (%s a %s) | TEST %d (%s a %s)",
        len(tr), tr.index.min().date(), tr.index.max().date(),
        len(va), va.index.min().date(), va.index.max().date(),
        len(te), te.index.min().date(), te.index.max().date(),
    )

    # --- modelo de AVALIACAO: so TRAIN, nunca viu VAL/TEST ---------------------
    modelo_avaliacao = Ridge(alpha=ALPHA_D7, random_state=RANDOM_STATE)
    modelo_avaliacao.fit(tr[FEATURES_D7], tr["target_d7"])

    pred_val = np.clip(modelo_avaliacao.predict(va[FEATURES_D7]), 0, None)
    pred_test = np.clip(modelo_avaliacao.predict(te[FEATURES_D7]), 0, None)
    metricas_val = calcular_metricas(va["target_d7"], pred_val)
    metricas_test = calcular_metricas(te["target_d7"], pred_test)

    log.info("VAL (avaliacao, fit so em TRAIN): %s", metricas_val)
    log.info("TEST (avaliacao, fit so em TRAIN, leitura unica): %s", metricas_test)

    # --- modelo de PRODUCAO: TRAIN+VAL (Secao 21 do notebook) ------------------
    treino_producao = pd.concat([tr, va])
    modelo_producao = Ridge(alpha=ALPHA_D7, random_state=RANDOM_STATE)
    modelo_producao.fit(treino_producao[FEATURES_D7], treino_producao["target_d7"])

    return {
        "modelo": modelo_producao,
        "metricas_val": metricas_val,
        "metricas_test": metricas_test,
        "periodo_treino_producao": {
            "inicio": str(treino_producao.index.min().date()),
            "fim": str(treino_producao.index.max().date()),
        },
    }


def salvar_artefato(resultado: dict) -> Path:
    """Grava model.pkl + metadata.json em models/volume_d7/v1/ e promove essa
    versao em current.json. Unico ponto deste modulo que grava em disco."""
    versao_dir = MODELS_DIR / NOME_MODELO / VERSAO
    versao_dir.mkdir(parents=True, exist_ok=True)

    pkl_path = versao_dir / "model.pkl"
    joblib.dump(resultado["modelo"], pkl_path)

    metadata = {
        "modelo": "ridge_d7",
        "versao": VERSAO,
        "tipo": "regressao",
        "target": "volume_total(t+7)",
        "features": FEATURES_D7,
        "hiperparametros": {"alpha": ALPHA_D7, "random_state": RANDOM_STATE},
        "periodo_treino": resultado["periodo_treino_producao"],
        "metricas_val": resultado["metricas_val"],
        "metricas_test": resultado["metricas_test"],
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
        "nota": (
            "metricas_val/metricas_test vem de um Ridge treinado SO em TRAIN "
            "(jan-out/2025) -- nunca viu VAL/TEST. E' a mesma avaliacao do "
            "notebook (Secoes 15-18), reproduzida aqui. O model.pkl persistido "
            "e' o modelo de PRODUCAO, retreinado em TRAIN+VAL (Secao 21 do "
            "notebook) -- por isso nao existe uma metrica de VAL 'do artefato "
            "persistido': o VAL ja fez parte do treino dele, medir nele seria "
            "in-sample."
        ),
    }
    metadata_path = versao_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    current_path = MODELS_DIR / NOME_MODELO / "current.json"
    current_path.write_text(json.dumps({"version": VERSAO}, indent=2), encoding="utf-8")

    log.info("Artefato salvo: %s (versao promovida em %s)", pkl_path, current_path)
    return pkl_path


def main() -> None:
    resultado = treinar()
    salvar_artefato(resultado)


if __name__ == "__main__":
    main()
