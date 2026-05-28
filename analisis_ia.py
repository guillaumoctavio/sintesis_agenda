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
MODELO = MODELO_IA

CAMPOS_REQUERIDOS = ["temas_clave", "actores_principales", "ambito", "relevancia_wolff", "resumen_ejecutivo"]


def validar_analisis(datos):
    if not isinstance(datos, dict):
        return False
    if not all(k in datos for k in CAMPOS_REQUERIDOS):
        return False
    if not isinstance(datos.get("temas_clave"), list):
        return False
    if not isinstance(datos.get("actores_principales"), list):
        return False
    # Normalizar ámbito: el modelo a veces devuelve "CABA | Nacional" o "Local"
    ambito_raw = datos.get("ambito", "")
    ambito_norm = _normalizar_ambito(ambito_raw)
    if not ambito_norm:
        return False
    datos["ambito"] = ambito_norm
    if datos.get("relevancia_wolff") not in ("Alta", "Media", "Baja"):
        return False
    if not isinstance(datos.get("resumen_ejecutivo"), str):
        return False
    if not datos.get("resumen_ejecutivo").strip():
        return False
    return True


def _normalizar_ambito(valor):
    """Mapea variantes del modelo al valor canónico."""
    VALIDOS = {"CABA", "Nacional", "Internacional"}
    if valor in VALIDOS:
        return valor
    v = valor.upper()
    if "CABA" in v:
        return "CABA"
    if "INTERN" in v:
        return "Internacional"
    if any(x in v for x in ("NACION", "LOCAL", "ARGENTIN", "DEPORT")):
        return "Nacional"
    return None


def analizar_noticia_con_ollama(titulo, cuerpo):
    texto_limpio = cuerpo[:LIMITE_CUERPO_CHARS] if cuerpo else ""

    prompt = f"""
Eres un analista político especializado en el ecosistema político de la Ciudad de Buenos Aires.
Trabajás para el equipo de Waldo Wolff: Legislador porteño, Presidente de la Comisión de Presupuesto de la Legislatura CABA, militante del PRO, ex Ministro de Seguridad porteño y referente de la comunidad judía argentina (DAIA, B'nai B'rith).

Lee la noticia y devolvé ÚNICAMENTE un objeto JSON válido, sin texto adicional ni markdown.

Criterios para "relevancia_wolff":
- "Alta": la noticia toca directamente CABA, el PRO, La Libertad Avanza en la Ciudad, presupuesto/coparticipación porteña, seguridad porteña, DAIA/comunidad judía, libertad de expresión, o legislatura CABA.
- "Media": toca política nacional con impacto indirecto en CABA o el PRO (economía nacional, relación Nación-Ciudad, elecciones 2027).
- "Baja": deportes, espectáculos, política de otras provincias sin vínculo con CABA o el PRO, internacional sin impacto local.

Estructura esperada:
{{
    "temas_clave": ["Tema 1", "Tema 2"],
    "actores_principales": ["Nombre (espacio político)"],
    "ambito": "CABA | Nacional | Internacional",
    "relevancia_wolff": "Alta | Media | Baja",
    "resumen_ejecutivo": "Máximo 4 líneas. Enfocado en qué implica para la Ciudad de Buenos Aires y el PRO."
}}

Título: {titulo}
Cuerpo: {texto_limpio}
"""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": TEMPERATURA_ANALISIS,
            "num_ctx": CTX_ANALISIS,
        },
    }

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=90)
        respuesta.raise_for_status()
        datos_json = json.loads(respuesta.json()["response"])

        if not validar_analisis(datos_json):
            logger.warning(f"JSON inválido o incompleto: {datos_json}")
            return None

        return datos_json

    except requests.exceptions.Timeout:
        logger.warning("Timeout: Ollama tardó más de 90s. Saltando nota.")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"JSON malformado devuelto por Ollama: {e}")
        return None
    except Exception as e:
        logger.error(f"Error en análisis IA: {e}")
        return None


def iniciar_analisis(dias=7):
    logger.info(f"=== INICIANDO ANALISTA IA — últimos {dias} días ===")

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        """SELECT id, titulo, cuerpo FROM noticias
           WHERE (resumen IS NULL OR resumen = 'Sin resumen')
             AND fecha_extraccion >= date('now', ?)""",
        (f"-{dias} days",),
    )
    noticias_pendientes = cursor.fetchall()
    conexion.close()

    if not noticias_pendientes:
        logger.info(f"No hay noticias pendientes en los últimos {dias} días.")
        return

    logger.info(f"{len(noticias_pendientes)} noticias pendientes de análisis.")

    for id_noticia, titulo, cuerpo in noticias_pendientes:
        logger.info(f"Analizando #{id_noticia}: {titulo[:60]}")

        analisis = analizar_noticia_con_ollama(titulo, cuerpo)

        if analisis:
            temas_texto = ", ".join(analisis.get("temas_clave", []))
            actores_texto = ", ".join(analisis.get("actores_principales", []))
            resumen_texto = analisis.get("resumen_ejecutivo", "Sin resumen")
            ambito_texto = analisis.get("ambito", "Nacional")
            relevancia_texto = analisis.get("relevancia_wolff", "Baja")

            # provincia_mencionada se mantiene igual a ambito para compatibilidad
            exito = database.guardar_analisis_ia(
                id_noticia,
                provincia=ambito_texto,
                temas=temas_texto,
                actores=actores_texto,
                resumen=resumen_texto,
                ambito=ambito_texto,
                relevancia=relevancia_texto,
            )
            if exito:
                logger.info(f"  [{relevancia_texto}] {ambito_texto} | {actores_texto[:40]}")
            else:
                logger.error(f"  Error al guardar análisis #{id_noticia} en BD.")
        else:
            logger.warning(f"  Sin análisis para #{id_noticia}, saltando.")

        time.sleep(PAUSA_ENTRE_REQUESTS)


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=7, help="Analizar noticias de los últimos N días (default: 7)")
    args = parser.parse_args()
    iniciar_analisis(dias=args.dias)
