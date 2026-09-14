"""Alerta operacional por e-mail (Plano 2.1, Etapa 15).

Um unico callback, compartilhado pelas 3 DAGs (``pipeline_incidentes_ti``,
``ml_previsao_volume``, ``ml_previsao_prioridade``) via
``default_args["on_failure_callback"]`` -- evita triplicar a logica de envio
e o texto do e-mail em cada arquivo de DAG.

Dispara SO na falha definitiva da task (todas as tentativas esgotadas),
nunca a cada retry: ``TaskInstance.is_eligible_to_retry()`` diz se o Airflow
ainda vai tentar de novo, e o callback nao envia nada nesse caso -- e' o
proprio Airflow (retries + is_eligible_to_retry) quem faz a deduplicacao,
sem necessidade de nenhuma tabela de controle nova.

E' um alerta OPERACIONAL (falha tecnica de execucao) -- nunca deve ser
confundido com um alerta de NEGOCIO (esses vem do Grafana Alerting, Etapa 15,
sobre os dados de gold.previsoes/gold.previsoes_prioridade). O corpo do
e-mail deixa isso explicito.
"""

from __future__ import annotations

import os

from airflow.utils.email import send_email

from config.logging import get_logger

log = get_logger(__name__)

_ASSUNTO = "[ALERTA OPERACIONAL] {dag_id} — {task_id} falhou"

_DISCLAIMER = (
    "Este e' um ALERTA OPERACIONAL (falha tecnica de execucao do pipeline) -- "
    "nao representa, por si so, um evento de negocio ou uma anomalia nos "
    "dados. Alertas de negocio (volume/erro de previsao acima do esperado) "
    "chegam separadamente pelo Grafana Alerting."
)


def _destinatarios() -> list[str]:
    bruto = os.getenv("ALERTA_EMAIL_DESTINATARIOS", "")
    return [e.strip() for e in bruto.split(",") if e.strip()]


def notificar_falha_operacional(context: dict) -> None:
    """Callback de ``on_failure_callback`` -- nao chamar diretamente."""
    task_instance = context["task_instance"]

    if task_instance.is_eligible_to_retry():
        log.info(
            "Falha em %s.%s ainda sera reprocessada (retry) -- nenhum "
            "e-mail enviado (so na falha definitiva).",
            context["dag"].dag_id, task_instance.task_id,
        )
        return

    destinatarios = _destinatarios()
    if not destinatarios:
        log.warning(
            "Falha definitiva em %s.%s, mas ALERTA_EMAIL_DESTINATARIOS esta "
            "vazio -- nenhum e-mail enviado.",
            context["dag"].dag_id, task_instance.task_id,
        )
        return

    dag_id = context["dag"].dag_id
    task_id = task_instance.task_id
    data_execucao = context.get("logical_date") or context.get("execution_date")
    excecao = context.get("exception")

    corpo = (
        f"<p><b>{_DISCLAIMER}</b></p>"
        f"<hr>"
        f"<p><b>DAG:</b> {dag_id}</p>"
        f"<p><b>Task:</b> {task_id}</p>"
        f"<p><b>Execucao:</b> {data_execucao}</p>"
        f"<p><b>Tentativa:</b> {task_instance.try_number}</p>"
        f"<p><b>Erro:</b> {excecao}</p>"
        f"<p><b>Log:</b> {task_instance.log_url}</p>"
    )

    send_email(
        to=destinatarios,
        subject=_ASSUNTO.format(dag_id=dag_id, task_id=task_id),
        html_content=corpo,
    )
    log.info("Alerta operacional enviado para %s (%s.%s)", destinatarios, dag_id, task_id)
