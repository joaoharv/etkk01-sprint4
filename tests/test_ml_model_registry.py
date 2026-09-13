"""Testes do Model Registry (src/ml/model_registry.py).

Nao dependem de banco nem de modelo real -- fabricam uma familia de modelo falsa em
tmp_path para validar so a cadeia de contrato (Plano 2.1). Nenhum .pkl de producao e
treinado aqui (isso e' escopo da Etapa 7/11).
"""

from __future__ import annotations

import json

import joblib
import pytest

from src.ml.model_registry import (
    CAMPOS_METADATA_OBRIGATORIOS,
    load_model,
    validar_features,
)

METADATA_VALIDA = {
    "modelo": "modelo_fake",
    "versao": "v1",
    "tipo": "regressao",
    "target": "volume_total(t+7)",
    "features": ["lag_1", "lag_7"],
    "hiperparametros": {"alpha": 1.0},
    "periodo_treino": {"inicio": "2025-01-01", "fim": "2025-10-31"},
    "metricas_val": {"MAE": 1.0},
    "metricas_test": {"MAE": 1.2},
    "sklearn_version": "1.9.1",
    "python_version": "3.11.9",
    "treinado_em": "2026-01-10T14:00:00",
}


def _cria_familia(tmp_path, nome="volume_d7", versao="v1", metadata=None, com_pkl=True,
                   com_metadata=True, com_current=True, aponta_para_versao=None):
    """Fabrica uma familia de modelo valida (ou propositalmente quebrada) em tmp_path."""
    base = tmp_path / "models"
    familia_dir = base / nome
    versao_dir = familia_dir / versao
    versao_dir.mkdir(parents=True)

    if com_current:
        current = {"version": aponta_para_versao or versao}
        (familia_dir / "current.json").write_text(json.dumps(current), encoding="utf-8")

    if com_pkl:
        joblib.dump({"fake": "modelo"}, versao_dir / "model.pkl")

    if com_metadata:
        conteudo = metadata if metadata is not None else METADATA_VALIDA
        (versao_dir / "metadata.json").write_text(json.dumps(conteudo), encoding="utf-8")

    return base


def test_load_model_caminho_feliz(tmp_path):
    base = _cria_familia(tmp_path)
    resultado = load_model("volume_d7", models_dir=base)

    assert resultado.modelo == {"fake": "modelo"}
    assert resultado.metadata["versao"] == "v1"
    assert resultado.caminho_pkl.name == "model.pkl"


def test_load_model_sem_current_json(tmp_path):
    base = _cria_familia(tmp_path, com_current=False)
    with pytest.raises(FileNotFoundError, match="current.json"):
        load_model("volume_d7", models_dir=base)


def test_load_model_versao_inexistente(tmp_path):
    base = _cria_familia(tmp_path, aponta_para_versao="v2")
    with pytest.raises(FileNotFoundError, match="v2"):
        load_model("volume_d7", models_dir=base)


def test_load_model_sem_pkl(tmp_path):
    base = _cria_familia(tmp_path, com_pkl=False)
    with pytest.raises(FileNotFoundError, match="model.pkl"):
        load_model("volume_d7", models_dir=base)


def test_load_model_sem_metadata(tmp_path):
    base = _cria_familia(tmp_path, com_metadata=False)
    with pytest.raises(FileNotFoundError, match="metadata.json"):
        load_model("volume_d7", models_dir=base)


def test_load_model_metadata_json_invalido(tmp_path):
    base = _cria_familia(tmp_path)
    (base / "volume_d7" / "v1" / "metadata.json").write_text("{nao e json valido", encoding="utf-8")
    with pytest.raises(ValueError, match="invalido"):
        load_model("volume_d7", models_dir=base)


@pytest.mark.parametrize("campo_ausente", CAMPOS_METADATA_OBRIGATORIOS)
def test_load_model_metadata_incompleta_falha_por_campo(tmp_path, campo_ausente):
    metadata_incompleta = {k: v for k, v in METADATA_VALIDA.items() if k != campo_ausente}
    base = _cria_familia(tmp_path, metadata=metadata_incompleta)
    with pytest.raises(ValueError, match=campo_ausente):
        load_model("volume_d7", models_dir=base)


def test_validar_features_ok_quando_conjuntos_batem():
    validar_features({"features": ["lag_1", "lag_7"]}, ["lag_7", "lag_1"])


def test_validar_features_falha_por_feature_faltando():
    with pytest.raises(ValueError, match="Faltando"):
        validar_features({"features": ["lag_1", "lag_7"]}, ["lag_1"])


def test_validar_features_falha_por_feature_sobrando_sem_subset_silencioso():
    with pytest.raises(ValueError, match="Sobrando"):
        validar_features({"features": ["lag_1"]}, ["lag_1", "lag_7"])
