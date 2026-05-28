"""
Pipeline completo multi-cliente:
  Stage 1 (compartido): scraping → análisis objetivo
  Stage 2 (por cliente): scoring relevancia → boletín → Telegram

Se ejecuta 3 veces por día vía cron (05h, 13h, 22h).

Uso:
    python3 pipeline.py               # todos los clientes activos, dias=1
    python3 pipeline.py --dias 2
    python3 pipeline.py --cliente wolff
"""
import argparse
import logging
from datetime import datetime

import analisis_objetivo
import analisis_clientes as analisis_clientes_mod
import boletin_ia
import orquestador
import telegram_notifier
import database
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from utils import setup_logging

logger = logging.getLogger(__name__)


def _notificar_cliente(cliente, ruta_boletin, hora_ciclo, duracion_min):
    """Envía el boletín al Telegram del cliente si tiene credenciales propias."""
    token = cliente.get("telegram_token") or TELEGRAM_TOKEN
    chat_id = cliente.get("telegram_chat_id") or TELEGRAM_CHAT_ID
    if not token or not chat_id:
        logger.warning(f"Cliente '{cliente['slug']}' sin Telegram configurado, omitiendo.")
        return
    # Reemplazar temporalmente las credenciales globales para este cliente
    import config
    orig_token, orig_chat = config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID
    config.TELEGRAM_TOKEN = token
    config.TELEGRAM_CHAT_ID = chat_id
    try:
        telegram_notifier.notificar_boletin(ruta_boletin, hora_ciclo=hora_ciclo, duracion_min=duracion_min)
    finally:
        config.TELEGRAM_TOKEN = orig_token
        config.TELEGRAM_CHAT_ID = orig_chat


def ejecutar_pipeline(dias=1, slug_cliente=None):
    inicio = datetime.now()
    hora_ciclo = inicio.strftime("%Hh")
    logger.info(f"=== PIPELINE — ciclo {hora_ciclo} | ventana {dias} día(s) ===")

    # ── STAGE 1: compartido para todos los clientes ──────────────────────────
    logger.info("--- STAGE 1a: Scraping ---")
    try:
        orquestador.iniciar_rutina_diaria()
    except Exception as e:
        logger.error(f"Scraping falló: {e}")

    logger.info("--- STAGE 1b: Análisis objetivo (neutro) ---")
    try:
        analisis_objetivo.iniciar_analisis_objetivo(dias=dias)
    except Exception as e:
        logger.error(f"Análisis objetivo falló: {e}")

    # ── STAGE 2: por cliente ─────────────────────────────────────────────────
    clientes = database.obtener_clientes_activos()
    if slug_cliente:
        clientes = [c for c in clientes if c["slug"] == slug_cliente]

    if not clientes:
        logger.warning("Sin clientes activos para Stage 2.")
        return

    logger.info(f"--- STAGE 2: {len(clientes)} cliente(s) activo(s) ---")

    logger.info("--- STAGE 2a: Scoring de relevancia por cliente ---")
    try:
        analisis_clientes_mod.iniciar_analisis_clientes(dias=dias, slug_cliente=slug_cliente)
    except Exception as e:
        logger.error(f"Scoring por cliente falló: {e}")

    duracion_stage1 = round((datetime.now() - inicio).total_seconds() / 60, 1)

    for cliente in clientes:
        logger.info(f"--- STAGE 2b: Boletín para '{cliente['slug']}' ---")
        try:
            ruta_boletin = boletin_ia.generar_boletin(slug_cliente=cliente["slug"], dias=dias)
            duracion_total = round((datetime.now() - inicio).total_seconds() / 60, 1)
            if ruta_boletin:
                logger.info(f"--- STAGE 2c: Telegram para '{cliente['slug']}' ---")
                _notificar_cliente(cliente, ruta_boletin, hora_ciclo, duracion_total)
            else:
                logger.warning(f"No se generó boletín para '{cliente['slug']}'.")
        except Exception as e:
            logger.error(f"Error en Stage 2 para '{cliente['slug']}': {e}")

    duracion_total = round((datetime.now() - inicio).total_seconds() / 60, 1)
    logger.info(f"=== Pipeline completado en {duracion_total} min ===")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Pipeline multi-cliente Síntesis Agenda")
    parser.add_argument("--dias", type=int, default=1, help="Ventana de días (default: 1)")
    parser.add_argument("--cliente", default=None, help="Slug del cliente (default: todos los activos)")
    args = parser.parse_args()
    ejecutar_pipeline(dias=args.dias, slug_cliente=args.cliente)
