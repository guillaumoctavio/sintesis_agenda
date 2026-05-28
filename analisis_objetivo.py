"""
Stage 1 — Análisis objetivo de noticias (compartido entre todos los clientes).

Extrae temas, actores, ámbito y resumen neutro de cada noticia sin aplicar
ningún criterio de relevancia específico de cliente.

Uso:
    python3 analisis_objetivo.py --dias 1
"""
import sqlite3
import requests
import json
import time
import argparse
import logging
import database
from config import (OLLAMA_URL, MODELO_IA, TEMPERATURA_ANALISIS, CTX_ANALISIS,
                    LIMITE_CUERPO_CHARS, PAUSA_ENTRE_REQUESTS, DB_PATH)
from utils import setup_logging

logger = logging.getLogger(__name__)

CAMPOS_REQUERIDOS = ["temas_clave", "actores_principales", "ambito", "resumen_ejecutivo"]
AMBITOS_VALIDOS = {"CABA", "Nacional", "Internacional"}


def _normalizar_ambito(valor):
    if valor in AMBITOS_VALIDOS:
        return valor
    v = str(valor).upper()
    if "CABA" in v:
        return "CABA"
    if "INTERN" in v:
        return "Internacional"
    return "Nacional"


def validar_analisis(datos):
    if not isinstance(datos, dict):
        return False
    if not all(k in datos for k in CAMPOS_REQUERIDOS):
        return False
    if not isinstance(datos.get("temas_clave"), list):
        return False
    if not isinstance(datos.get("actores_principales"), list):
        return False
    if not isinstance(datos.get("resumen_ejecutivo"), str):
        return False
    if not datos.get("resumen_ejecutivo", "").strip():
        return False
    datos["ambito"] = _normalizar_ambito(datos.get("ambito", "Nacional"))
    return True


def analizar_noticia(titulo, cuerpo):
    texto = cuerpo[:LIMITE_CUERPO_CHARS] if cuerpo else ""

    prompt = f"""Eres un analista de medios especializado en política argentina.
Lee la siguiente noticia y devolvé ÚNICAMENTE un objeto JSON válido, sin texto adicional ni markdown.

Estructura esperada:
{{
    "temas_clave": ["Tema 1", "Tema 2"],
    "actores_principales": ["Nombre (rol/espacio político)"],
    "ambito": "CABA | Nacional | Internacional",
    "resumen_ejecutivo": "Máximo 4 líneas. Qué pasó, quiénes están involucrados y qué implica."
}}

Título: {titulo}
Cuerpo: {texto}
"""

    payload = {
        "model": MODELO_IA,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": TEMPERATURA_ANALISIS, "num_ctx": CTX_ANALISIS},
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=90)
        r.raise_for_status()
        datos = json.loads(r.json()["response"])
        if not validar_analisis(datos):
            logger.warning(f"JSON inválido: {datos}")
            return None
        return datos
    except requests.exceptions.Timeout:
        logger.warning("Timeout: Ollama tardó más de 90s. Saltando.")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"JSON malformado: {e}")
        return None
    except Exception as e:
        logger.error(f"Error en análisis objetivo: {e}")
        return None


def iniciar_analisis_objetivo(dias=1):
    logger.info(f"=== STAGE 1 — ANÁLISIS OBJETIVO — últimos {dias} días ===")

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        """SELECT id, titulo, cuerpo FROM noticias
           WHERE (resumen IS NULL OR resumen = 'Sin resumen' OR resumen = 'Omitido')
             AND fecha_extraccion >= date('now', ?)""",
        (f"-{dias} days",),
    )
    pendientes = cursor.fetchall()
    conexion.close()

    if not pendientes:
        logger.info("No hay noticias pendientes de análisis objetivo.")
        return

    logger.info(f"{len(pendientes)} noticias pendientes.")

    for id_noticia, titulo, cuerpo in pendientes:
        logger.info(f"Analizando #{id_noticia}: {titulo[:60]}")

        analisis = analizar_noticia(titulo, cuerpo)

        if analisis:
            temas = ", ".join(analisis.get("temas_clave", []))
            actores = ", ".join(analisis.get("actores_principales", []))
            resumen = analisis.get("resumen_ejecutivo", "")
            ambito = analisis.get("ambito", "Nacional")

            exito = database.guardar_analisis_objetivo(id_noticia, temas, actores, resumen, ambito)
            if exito:
                logger.info(f"  [{ambito}] {actores[:50]}")
            else:
                logger.error(f"  Error al guardar análisis #{id_noticia}.")
        else:
            logger.warning(f"  Sin análisis para #{id_noticia}, saltando.")

        time.sleep(PAUSA_ENTRE_REQUESTS)


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Stage 1: análisis objetivo de noticias")
    parser.add_argument("--dias", type=int, default=1, help="Ventana de días hacia atrás (default: 1)")
    args = parser.parse_args()
    iniciar_analisis_objetivo(dias=args.dias)
