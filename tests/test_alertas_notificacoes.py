"""Testes do alerta operacional por e-mail (Plano 2.1, Etapa 15).

Mocka ``send_email`` de proposito (unico teste do projeto que faz isso):
diferente dos testes de integracao de banco (sempre contra o Postgres real),
aqui o efeito colateral e' enviar e-mail via SMTP -- nao faz sentido depender
de um servidor de e-mail estar de pe so para testar a LOGICA do callback
(formato do assunto/corpo, quando envia ou nao). O envio real e' validado
separadamente pelo teste manual com Mailpit (relatorio da Etapa 15).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.alertas.notificacoes import notificar_falha_operacional


class _TaskInstanceFalsa:
    def __init__(self, *, elegivel_a_retry: bool, try_number: int = 1):
        self.task_id = "task_exemplo"
        self.try_number = try_number
        self.log_url = "http://airflow.local/log/exemplo"
        self._elegivel = elegivel_a_retry

    def is_eligible_to_retry(self) -> bool:
        return self._elegivel


class _DagFalsa:
    dag_id = "dag_exemplo"


def _context(*, elegivel_a_retry: bool) -> dict:
    return {
        "task_instance": _TaskInstanceFalsa(elegivel_a_retry=elegivel_a_retry),
        "dag": _DagFalsa(),
        "logical_date": "2026-01-01T00:00:00+00:00",
        "exception": ValueError("falha simulada"),
    }


@pytest.fixture(autouse=True)
def _destinatarios_padrao(monkeypatch):
    monkeypatch.setenv("ALERTA_EMAIL_DESTINATARIOS", "oncall@sprint4.local, outro@sprint4.local")


def test_nao_envia_enquanto_ainda_havera_retry():
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=True))
    mock_send.assert_not_called()


def test_envia_exatamente_uma_vez_na_falha_definitiva():
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=False))
    mock_send.assert_called_once()


def test_assunto_segue_o_formato_exigido():
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=False))
    _, kwargs = mock_send.call_args
    assert kwargs["subject"] == "[ALERTA OPERACIONAL] dag_exemplo — task_exemplo falhou"


def test_corpo_contem_o_disclaimer_de_alerta_operacional():
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=False))
    _, kwargs = mock_send.call_args
    assert "ALERTA OPERACIONAL" in kwargs["html_content"]
    assert "nao representa" in kwargs["html_content"] or "não representa" in kwargs["html_content"]


def test_destinatarios_vem_da_variavel_de_ambiente():
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=False))
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == ["oncall@sprint4.local", "outro@sprint4.local"]


def test_nao_envia_se_nenhum_destinatario_configurado(monkeypatch):
    monkeypatch.setenv("ALERTA_EMAIL_DESTINATARIOS", "")
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=False))
    mock_send.assert_not_called()


def test_corpo_nunca_expoe_segredos_de_ambiente(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "__segredo_teste__")
    monkeypatch.setenv("AIRFLOW_SECRET_KEY", "__outro_segredo_teste__")
    with patch("src.alertas.notificacoes.send_email") as mock_send:
        notificar_falha_operacional(_context(elegivel_a_retry=False))
    _, kwargs = mock_send.call_args
    assert "__segredo_teste__" not in kwargs["html_content"]
    assert "__outro_segredo_teste__" not in kwargs["html_content"]
