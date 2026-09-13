"""Calculo de metricas de ML (Plano 2.1) -- mesma formula dos notebooks.

Compartilhado entre os modulos de treino (avaliacao em tempo de treino) e de
inferencia (avaliacao OOS em tempo de inferencia) de cada modelo, para
garantir que as duas etapas nunca divirjam silenciosamente na formula.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    recall_score,
)


def calcular_metricas(y_true, y_pred) -> dict:
    """MAE, RMSE, sMAPE e R2 -- mesma formula da Secao 13 do notebook."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    denom = np.abs(y_true) + np.abs(y_pred)
    smape = float(np.mean(np.where(denom == 0, 0.0, 2 * np.abs(y_pred - y_true) / denom)) * 100)
    r2 = float(r2_score(y_true, y_pred)) if len(y_true) > 1 else float("nan")

    return {
        "MAE": round(float(mae), 3),
        "RMSE": round(rmse, 3),
        "sMAPE_%": round(smape, 3),
        "R2": round(r2, 3),
        "n": int(len(y_true)),
    }


def calcular_metricas_classificacao(y_true, y_pred, labels: list[str]) -> dict:
    """Accuracy, F1-Macro, F1-Weighted, Balanced Accuracy e Recall por classe --
    mesmas metricas COMPLETE do notebook 02 (funcao ``calcular_metricas`` do
    notebook, celula 40). Nao reproduz o recorte SEEN/NEW (cortado do escopo
    de producao na Etapa 5 -- exigiria persistir o vocabulario do TRAIN como
    artefato extra so para uma coluna analitica)."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    recall_por_classe = dict(zip(labels, recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)))

    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 3),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 3),
        "f1_macro": round(float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 3),
        "f1_weighted": round(float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)), 3),
        "recall_por_classe": {k: round(float(v), 3) for k, v in recall_por_classe.items()},
        "n": int(len(y_true)),
    }
