"""Treino do modelo de classificacao de Prioridade (Plano 2.1, Etapa 11).

Reproduz FIELMENTE o pipeline final do notebook 02 (celulas 87-90, saida real
de execucao): TF-IDF(ngram=(1,2), min_df=1, max_features=20000) + Produto
(OneHotEncoder) -> LinearSVC(C=2.0, class_weight=None). Hiperparametros
hardcoded a partir do que o notebook ja reportou como vencedor -- nao
re-otimizados nesta etapa.

Diferenca real em relacao ao modelo de volume (train_volume.py): o notebook
02 NAO tem um "refit de producao em TRAIN+VAL" (ao contrario do notebook 01,
Secao 21) -- o pipeline final e' ajustado UMA VEZ, so em TRAIN (set+out/2025),
e avaliado em VAL (tuning) e TEST (celula 92, leitura unica). Reproduzir aqui
um refit em TRAIN+VAL seria inventar uma etapa que o notebook nao tem -- por
isso o artefato persistido e' o MESMO fit usado para reportar as metricas
(nao existe a distincao "modelo de avaliacao" vs "modelo de producao" deste
lado).

O proprio notebook classifica este pipeline como "Experimental" (Secao 17) --
nao "Recomendado": F1-Macro cai de 0.889 (VAL) para 0.735 (TEST) por causa de
drift documentado. Isso e' comunicado explicitamente no metadata.json e deve
aparecer no Grafana como "piloto assistido", nunca decisao automatica.

Roda SEMPRE dentro do container Airflow (nunca no host):

    docker compose exec airflow-webserver python -m src.ml.train_prioridade
"""

from __future__ import annotations

import json
import platform
from datetime import datetime
from pathlib import Path

import joblib
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.svm import LinearSVC

from config.logging import get_logger
from src.ml.features.prioridade_features import (
    CLASSES_ALVO,
    FEATURES_PRIORIDADE,
    carregar_populacao_prioridade,
    preparar_features_prioridade,
    split_temporal_prioridade,
)
from src.ml.metrics import calcular_metricas_classificacao

log = get_logger(__name__)

# Hiperparametros EXATOS reportados pela execucao real do notebook (celula 87:
# "Config vencedora: C=2.0, ngram_range=(1, 2), min_df=1, max_features=20000").
# NAO re-otimizados nesta etapa.
C_FINAL = 2.0
NGRAM_RANGE_FINAL = (1, 2)
MIN_DF_FINAL = 1
MAX_FEATURES_FINAL = 20000
RANDOM_STATE = 42
CLASS_WEIGHT = None

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
NOME_MODELO = "prioridade"
VERSAO = "v1"


def construir_pipeline() -> Pipeline:
    """TF-IDF(descricao_resumida) + OneHot(produto_prep) -> LinearSVC.
    Mesma arquitetura do pipeline vencedor do notebook (E03/celula 90)."""
    pre = ColumnTransformer([
        (
            "texto",
            TfidfVectorizer(
                ngram_range=NGRAM_RANGE_FINAL,
                min_df=MIN_DF_FINAL,
                max_features=MAX_FEATURES_FINAL,
            ),
            "descricao_resumida",
        ),
        ("produto", OneHotEncoder(handle_unknown="ignore"), ["produto_prep"]),
    ])
    modelo = LinearSVC(C=C_FINAL, class_weight=CLASS_WEIGHT, random_state=RANDOM_STATE)
    return Pipeline([("features", pre), ("modelo", modelo)])


def treinar() -> dict:
    populacao = carregar_populacao_prioridade()
    features = preparar_features_prioridade(populacao)
    alvo = populacao["prioridade"]

    train, val, test = split_temporal_prioridade(populacao)
    log.info(
        "Split temporal: TRAIN %d (%s a %s) | VAL %d (%s a %s) | TEST %d (%s a %s)",
        len(train), train["aberto"].min(), train["aberto"].max(),
        len(val), val["aberto"].min(), val["aberto"].max(),
        len(test), test["aberto"].min(), test["aberto"].max(),
    )

    X_train, y_train = features.loc[train.index], alvo.loc[train.index]
    X_val, y_val = features.loc[val.index], alvo.loc[val.index]
    X_test, y_test = features.loc[test.index], alvo.loc[test.index]

    pipeline = construir_pipeline()
    pipeline.fit(X_train, y_train)

    pred_val = pipeline.predict(X_val)
    pred_test = pipeline.predict(X_test)

    metricas_val = calcular_metricas_classificacao(y_val, pred_val, list(CLASSES_ALVO))
    metricas_test = calcular_metricas_classificacao(y_test, pred_test, list(CLASSES_ALVO))

    log.info("VAL (fit so em TRAIN): %s", metricas_val)
    log.info("TEST (fit so em TRAIN, leitura unica): %s", metricas_test)

    return {
        "modelo": pipeline,
        "metricas_val": metricas_val,
        "metricas_test": metricas_test,
        "periodo_treino": {
            "inicio": str(train["aberto"].min().date()),
            "fim": str(train["aberto"].max().date()),
        },
    }


def salvar_artefato(resultado: dict) -> Path:
    versao_dir = MODELS_DIR / NOME_MODELO / VERSAO
    versao_dir.mkdir(parents=True, exist_ok=True)

    pkl_path = versao_dir / "model.pkl"
    joblib.dump(resultado["modelo"], pkl_path)

    metadata = {
        "modelo": "linearsvc_prioridade",
        "versao": VERSAO,
        "tipo": "classificacao",
        "target": "Prioridade (2 - Alta / 3 - Média / 4 - Baixa)",
        "features": FEATURES_PRIORIDADE,
        "hiperparametros": {
            "C": C_FINAL,
            "class_weight": CLASS_WEIGHT,
            "random_state": RANDOM_STATE,
            "ngram_range": list(NGRAM_RANGE_FINAL),
            "min_df": MIN_DF_FINAL,
            "max_features": MAX_FEATURES_FINAL,
        },
        "periodo_treino": resultado["periodo_treino"],
        "metricas_val": resultado["metricas_val"],
        "metricas_test": resultado["metricas_test"],
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
        "nota": (
            "O notebook 02 classifica este pipeline como 'Experimental' (nao "
            "'Recomendado'): F1-Macro cai de 0.889 (VAL) para 0.735 (TEST) por "
            "drift documentado (Secao 14 do notebook). Nao existe refit de "
            "producao em TRAIN+VAL para este modelo (diferente do volume_d7) "
            "-- o notebook nunca fez isso, entao nao e' reproduzido aqui. "
            "Uso recomendado: piloto assistido de triagem, com validacao "
            "humana -- NUNCA decisao automatica. score_vencedor vem de "
            "LinearSVC.decision_function(), NAO e' probabilidade."
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
