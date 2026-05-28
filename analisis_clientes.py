"""
Stage 2 — Scoring de relevancia por cliente.

Para cada cliente activo, toma las noticias con análisis objetivo (Stage 1)
y aplica los criterios del cliente para asignar relevancia y generar un
resumen enfocado en su perfil.

Uso:
    python3 analisis_clientes.py --dias 1
    python3 analisis_clientes.py --dias 1 --cliente wolff
"""
import sqlite3
import requests
import json
import time
import argparse
import logging
import database
from config import (OLLAMA_URL, MODELO_IA, TEMPERATURA_ANALISIS, CTX_ANALISIS,
                    PAUSA_ENTRE_REQUESTS, DB_PATH)
from utils import setup_logging

logger = logging.getLogger(__name__)


def _construir_prompt(cliente, titulo, temas, actores, ambito, resumen_objetivo):
    return f"""Sos un analista político trabajando para {cliente['nombre']}.

PERFIL DEL CLIENTE:
{cliente['perfil']}

CRITERIOS DE RELEVANCIA:
- Alta: {cliente['criterios_alta']}
- Media: {cliente['criterios_media']}
- Baja: todo lo demás (deportes, espectáculos, provincias sin vínculo)

Leé los datos de la noticia y devolvé ÚNICAMENTE un JSON válido, sin texto adicional.

Estructura esperada:
{{
    "relevancia": "Alta | Media | Baja",
    "resumen_cliente": "Máximo 4 líneas enfocadas en qué implica esta noticia para {cliente['nombre']}. Si es Baja relevancia, escribí una línea breve."
}}

NOTICIA:
Título: {titulo}
Temas: {temas}
Actores: {actores}
Ámbito: {ambito}
Resumen objetivo: {resumen_objetivo}
"""


def _validar_resultado(datos):
    if not isinstance(datos, dict):
        return False
    if datos.get("relevancia") not in ("Alta", "Media", "Baja"):
        return False
    if not isinstance(datos.get("resumen_cliente"), str):
        return False
    if not datos.get("resumen_cliente", "").strip():
        return False
    return True


def analizar_para_cliente(cliente, titulo, temas, actores, ambito, resumen_objetivo):
    prompt = _construir_prompt(cliente, titulo, temas, actores, ambito, resumen_objetivo)
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
        if not _validar_resultado(datos):
            logger.warning(f"JSON inválido para cliente {cliente['slug']}: {datos}")
            return None
        return datos
    except requests.exceptions.Timeout:
        logger.warning("Timeout Ollama. Saltando.")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"JSON malformado: {e}")
        return None
    except Exception as e:
        logger.error(f"Error en análisis cliente: {e}")
        return None


def iniciar_analisis_clientes(dias=1, slug_cliente=None):
    logger.info(f"=== STAGE 2 — ANÁLISIS POR CLIENTE — últimos {dias} días ===")

    if slug_cliente:
        clientes = [database.obtener_cliente(slug_cliente)]
        clientes = [c for c in clientes if c]
    else:
        clientes = database.obtener_clientes_activos()

    if not clientes:
        logger.warning("No hay clientes activos configurados.")
        return

    logger.info(f"Clientes activos: {[c['slug'] for c in clientes]}")

    for cliente in clientes:
        logger.info(f"--- Procesando cliente: {cliente['nombre']} ({cliente['slug']}) ---")

        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()
        cursor.execute(
            """SELECT n.id, n.titulo, n.temas, n.actores, n.ambito, n.resumen
               FROM noticias n
               LEFT JOIN analisis_clientes ac
                 ON ac.noticia_id = n.id AND ac.cliente_id = ?
               WHERE n.resumen IS NOT NULL
                 AND n.resumen NOT IN ('Sin resumen', 'Omitido', '')
                 AND n.fecha_extraccion >= date('now', ?)
                 AND ac.id IS NULL""",
            (cliente["id"], f"-{dias} days"),
        )
        pendientes = cursor.fetchall()
        conexion.close()

        if not pendientes:
            logger.info(f"  Sin noticias pendientes para {cliente['slug']}.")
            continue

        logger.info(f"  {len(pendientes)} noticias para clasificar.")

        for noticia_id, titulo, temas, actores, ambito, resumen_obj in pendientes:
            resultado = analizar_para_cliente(
                cliente, titulo, temas or "", actores or "", ambito or "", resumen_obj or ""
            )

            if resultado:
                relevancia = resultado["relevancia"]
                resumen_c = resultado["resumen_cliente"]
                database.guardar_analisis_cliente(noticia_id, cliente["id"], relevancia, resumen_c)
                logger.info(f"  #{noticia_id} [{relevancia}] {titulo[:50]}")
            else:
                logger.warning(f"  Sin resultado para #{noticia_id}, saltando.")

            time.sleep(PAUSA_ENTRE_REQUESTS)

    logger.info("=== Stage 2 completado ===")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Stage 2: scoring de relevancia por cliente")
    parser.add_argument("--dias", type=int, default=1, help="Ventana de días (default: 1)")
    parser.add_argument("--cliente", default=None, help="Slug del cliente (default: todos los activos)")
    args = parser.parse_args()
    iniciar_analisis_clientes(dias=args.dias, slug_cliente=args.cliente)
