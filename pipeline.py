"""
Pipeline completo: scraping → análisis IA → boletín → notificación Telegram.
Se ejecuta 3 veces por día vía cron (05h, 13h, 22h).

Uso:
    python3 pipeline.py           # días=1 por defecto
    python3 pipeline.py --dias 2  # ampliar ventana de noticias
"""
import argparse
import logging
import subprocess
import sys
from datetime import datetime

import analisis_ia
import orquestador
import boletin_ia
import telegram_notifier
from utils import setup_logging

logger = logging.getLogger(__name__)


def ejecutar_pipeline(dias=1):
    inicio = datetime.now()
    hora_ciclo = inicio.strftime("%Hh")
    logger.info(f"=== PIPELINE — ciclo {hora_ciclo} | ventana {dias} día(s) ===")

    # Etapa 1: scraping
    logger.info("--- ETAPA 1: Scraping ---")
    try:
        orquestador.iniciar_rutina_diaria()
    except Exception as e:
        logger.error(f"Scraping falló: {e}")

    # Etapa 2: análisis IA
    logger.info("--- ETAPA 2: Análisis IA ---")
    try:
        analisis_ia.iniciar_analisis(dias=dias)
    except Exception as e:
        logger.error(f"Análisis IA falló: {e}")

    # Etapa 3: generación del boletín
    logger.info("--- ETAPA 3: Boletín ---")
    ruta_boletin = None
    try:
        ruta_boletin = boletin_ia.generar_boletin_premium(dias=dias)
    except Exception as e:
        logger.error(f"Boletín falló: {e}")

    duracion = round((datetime.now() - inicio).total_seconds() / 60, 1)

    # Etapa 4: notificación Telegram
    if ruta_boletin:
        logger.info("--- ETAPA 4: Notificación Telegram ---")
        telegram_notifier.notificar_boletin(ruta_boletin, hora_ciclo=hora_ciclo, duracion_min=duracion)
    else:
        logger.warning("No se generó boletín, omitiendo notificación.")

    logger.info(f"=== Pipeline completado en {duracion} min ===")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Pipeline completo de Síntesis Agenda")
    parser.add_argument("--dias", type=int, default=1, help="Ventana de días hacia atrás (default: 1)")
    args = parser.parse_args()
    ejecutar_pipeline(dias=args.dias)
