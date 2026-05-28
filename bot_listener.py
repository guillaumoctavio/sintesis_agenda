"""
Bot de Telegram con comandos interactivos.
Responde a mensajes entrantes y ejecuta acciones del pipeline.

Comandos disponibles:
    /start   — Bienvenida
    /estado  — Estado del sistema y estadísticas de la BD
    /hoy     — Genera y envía el boletín del día ahora mismo
    /semanal — Genera y envía el informe estratégico semanal
    /ayuda   — Lista de comandos

Ejecutar como servicio:
    python3 bot_listener.py

O en background:
    nohup python3 bot_listener.py >> logs/bot.log 2>&1 &
"""
import logging
import sqlite3
import time
import threading
from datetime import datetime

import requests

import pipeline
import reporte_semanal
import telegram_notifier
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DB_PATH
from utils import setup_logging

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3  # segundos entre cada consulta a Telegram
COMANDOS = {
    "/start":   "Bienvenida al bot",
    "/estado":  "Estado del sistema y estadísticas",
    "/hoy":     "Genera el boletín del día y lo envía",
    "/semanal": "Genera el informe semanal y lo envía",
    "/ayuda":   "Lista de comandos disponibles",
}

_ultimo_update_id = None
_pipeline_corriendo = False


def _get_updates(offset=None):
    params = {"timeout": 20, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("result", [])
    except Exception as e:
        logger.warning(f"Error polling Telegram: {e}")
        return []


def _responder(chat_id, texto):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception as e:
        logger.error(f"Error respondiendo a {chat_id}: {e}")


def _stats_db():
    try:
        con = sqlite3.connect(DB_PATH)
        total = con.execute("SELECT COUNT(*) FROM noticias").fetchone()[0]
        hoy = con.execute(
            "SELECT COUNT(*) FROM noticias WHERE fecha_extraccion >= date('now', '-1 days')"
        ).fetchone()[0]
        alta = con.execute(
            "SELECT COUNT(*) FROM noticias WHERE relevancia='Alta' AND fecha_extraccion >= date('now', '-7 days')"
        ).fetchone()[0]
        media = con.execute(
            "SELECT COUNT(*) FROM noticias WHERE relevancia='Media' AND fecha_extraccion >= date('now', '-7 days')"
        ).fetchone()[0]
        pendientes = con.execute(
            "SELECT COUNT(*) FROM noticias WHERE (resumen IS NULL OR resumen='Sin resumen') AND fecha_extraccion >= date('now', '-1 days')"
        ).fetchone()[0]
        con.close()
        return total, hoy, alta, media, pendientes
    except Exception as e:
        logger.error(f"Error leyendo BD: {e}")
        return 0, 0, 0, 0, 0


def manejar_comando(chat_id, texto):
    global _pipeline_corriendo
    comando = texto.strip().split()[0].lower()

    if comando == "/start":
        _responder(chat_id, (
            "👋 Bienvenido a *Síntesis Agenda*\n\n"
            "Monitoreo político automatizado. Rastreo diarios argentinos, "
            "analizo con IA y te mando el informe ejecutivo al teléfono.\n\n"
            "📋 *Comandos disponibles:*\n"
            "/estado — Estado del sistema\n"
            "/ayuda — Esta lista"
        ))

    elif comando == "/ayuda":
        _responder(chat_id, (
            "📋 *Comandos disponibles:*\n\n"
            "/estado — Estado del sistema y estadísticas\n"
            "/ayuda — Esta lista de comandos\n\n"
            "_Los boletines automáticos llegan a las 05h, 13h y 22h._"
        ))

    elif comando == "/estado":
        total, hoy, alta, media, pendientes = _stats_db()
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        estado_pipeline = "🔄 Corriendo" if _pipeline_corriendo else "✅ Disponible"
        _responder(chat_id, (
            f"📊 *Estado del sistema* — {ahora}\n\n"
            f"🗄️ *Base de datos:*\n"
            f"  Total noticias: {total:,}\n"
            f"  Últimas 24h: {hoy}\n"
            f"  Pendientes análisis: {pendientes}\n\n"
            f"📰 *Esta semana (relevantes):*\n"
            f"  🔴 Alta: {alta}\n"
            f"  🟡 Media: {media}\n\n"
            f"⚙️ Pipeline: {estado_pipeline}"
        ))

    else:
        _responder(chat_id, f"❓ Comando no reconocido: `{comando}`\nUsá /ayuda para ver los comandos disponibles.")


def iniciar_bot():
    global _ultimo_update_id
    logger.info("=== BOT LISTENER iniciado. Esperando comandos... ===")

    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN no configurado. Saliendo.")
        return

    while True:
        updates = _get_updates(offset=_ultimo_update_id)
        for update in updates:
            _ultimo_update_id = update["update_id"] + 1
            mensaje = update.get("message", {})
            texto = mensaje.get("text", "").strip()
            chat_id = mensaje.get("chat", {}).get("id")

            if not texto or not chat_id or not texto.startswith("/"):
                continue

            logger.info(f"Comando recibido de {chat_id}: {texto}")
            manejar_comando(chat_id, texto)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    setup_logging()
    iniciar_bot()
