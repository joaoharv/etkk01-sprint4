"""Model Registry: carrega artefatos de ML (model.pkl + metadata.json) com validacao explicita.

Sem MLflow -- versionamento por pasta (models/<familia>/<versao>/), promovido a "vigente"
editando models/<familia>/current.json manualmente. Nenhuma etapa desta cadeia falha em
silencio: cada arquivo ausente ou incompativel levanta um erro explicito e acionavel, no
mesmo estilo de src/db.py (_require). Ver models/README.md para o contrato completo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

from config.logging import get_logger

log = get_logger(__name__)

_MODELS_DIR_PADRAO = Path(__file__).resolve().parents[2] / "models"

CAMPOS_METADATA_OBRIGATORIOS = (
    "modelo",
    "versao",
    "tipo",
    "target",
    "features",
    "hiperparametros",
    "periodo_treino",
    "metricas_val",
    "metricas_test",
    "sklearn_version",
    "python_version",
    "treinado_em",
)


@dataclass(frozen=True)
class ModeloCarregado:
    """Retorno de load_model(): o modelo desserializado e o metadata que o descreve."""

    modelo: Any
    metadata: dict
    caminho_pkl: Path


def load_model(nome: str, models_dir: str | Path | None = None) -> ModeloCarregado:
    """Carrega o modelo *vigente* da familia `nome` (ex.: 'volume_d7', 'prioridade').

    Cadeia de validacao (Plano 2.1): current.json -> versao -> model.pkl -> metadata.json
    -> metadata completo -> joblib.load(). Qualquer etapa que falhar levanta um erro
    explicito -- nunca um fallback ou subset silencioso.
    """
    base = Path(models_dir) if models_dir is not None else _MODELS_DIR_PADRAO
    familia_dir = base / nome

    current_path = familia_dir / "current.json"
    if not current_path.is_file():
        raise FileNotFoundError(
            f"current.json nao encontrado para o modelo '{nome}' em {current_path}. "
            "Treine e promova uma versao antes de rodar a inferencia "
            "(ver models/README.md)."
        )

    try:
        current = json.loads(current_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"current.json invalido em {current_path}: {exc}") from exc

    versao = current.get("version")
    if not versao:
        raise ValueError(f"{current_path} nao tem a chave 'version'.")

    versao_dir = familia_dir / versao
    if not versao_dir.is_dir():
        raise FileNotFoundError(
            f"Versao '{versao}' apontada por {current_path} nao existe em {versao_dir}."
        )

    pkl_path = versao_dir / "model.pkl"
    if not pkl_path.is_file():
        raise FileNotFoundError(f"model.pkl nao encontrado em {pkl_path}.")

    metadata_path = versao_dir / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"metadata.json nao encontrado em {metadata_path}.")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"metadata.json invalido em {metadata_path}: {exc}") from exc

    faltando = [c for c in CAMPOS_METADATA_OBRIGATORIOS if c not in metadata]
    if faltando:
        raise ValueError(
            f"metadata.json em {metadata_path} esta incompleto. "
            f"Campos obrigatorios ausentes: {faltando}"
        )

    modelo = joblib.load(pkl_path)
    log.info(
        "Modelo carregado: %s versao=%s tipo=%s treinado_em=%s",
        nome, metadata["versao"], metadata["tipo"], metadata["treinado_em"],
    )
    return ModeloCarregado(modelo=modelo, metadata=metadata, caminho_pkl=pkl_path)


def validar_features(metadata: dict, colunas_produzidas: list[str]) -> None:
    """Garante que as features produzidas batem EXATAMENTE com metadata['features'].

    Nunca faz subset silencioso: falta ou sobra de coluna e' erro, nao warning.
    """
    esperadas = set(metadata["features"])
    produzidas = set(colunas_produzidas)
    if esperadas != produzidas:
        faltando = sorted(esperadas - produzidas)
        sobrando = sorted(produzidas - esperadas)
        raise ValueError(
            "Features produzidas nao batem com metadata.json (contrato do Model Registry). "
            f"Faltando: {faltando}. Sobrando: {sobrando}."
        )
