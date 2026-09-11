"""Logging compartilhado do projeto.

Uso:
    from config.logging import get_logger
    log = get_logger(__name__)
    log.info("Bronze carregada: %d linhas", n)

Formato unico: ``timestamp | nivel | nome | mensagem``.
Nivel controlado pela variavel de ambiente ``LOG_LEVEL`` (default ``INFO``).
"""

from __future__ import annotations

import logging
import os
import sys

_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _level() -> int:
    nome = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, nome, logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger nomeado com o formato padrao do projeto.

    Quando roda dentro do Airflow (root logger ja configurado), apenas ajusta o
    nivel e deixa a mensagem propagar para os handlers do Airflow. Quando roda
    standalone (script, pytest), adiciona um handler proprio para o stdout.
    """
    logger = logging.getLogger(name)
    logger.setLevel(_level())

    ja_configurado = bool(logging.getLogger().handlers) or bool(logger.handlers)
    if not ja_configurado:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        logger.addHandler(handler)

    return logger
