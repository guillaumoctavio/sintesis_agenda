"""
Generador de informe estratégico semanal.
Consulta la BD por los últimos 7 días y produce un análisis de tendencias
más profundo que el boletín diario.

Uso:
    python3 reporte_semanal.py
    python3 reporte_semanal.py --semana 2026-W22  # semana específica
    python3 reporte_semanal.py --sin-telegram      # solo guardar, no enviar
"""
import os
import sqlite3
import requests
import time
import argparse
import logging
from datetime import datetime, timedelta

import telegram_notifier
from config import OLLAMA_URL, MODELO_IA, CTX_BOLETIN, DB_PATH, REPORTES_DIR
from utils import setup_logging

logger = logging.getLogger(__name__)
MODELO = MODELO_IA
LIMITE_NOTICIAS = 80


def get_rango_semana(semana_iso=None):
    """Devuelve (fecha_inicio, fecha_fin, label) para la semana dada o la actual."""
    if semana_iso:
        año, num_semana = semana_iso.split("-W")
        # Lunes de esa semana ISO
        inicio = datetime.strptime(f"{año}-W{num_semana}-1", "%Y-W%W-%w")
        fin = inicio + timedelta(days=6)
    else:
        hoy = datetime.now()
        inicio = hoy - timedelta(days=hoy.weekday())  # lunes
        fin = inicio + timedelta(days=6)
        semana_iso = hoy.strftime("%Y-W%V")
    return inicio.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d"), semana_iso


def generar_reporte_semanal(semana_iso=None, enviar_telegram=True):
    fecha_inicio, fecha_fin, semana_label = get_rango_semana(semana_iso)
    logger.info(f"=== REPORTE SEMANAL {semana_label} ({fecha_inicio} → {fecha_fin}) ===")

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        """SELECT diario, titulo, temas, actores, ambito, relevancia, resumen, link
           FROM noticias
           WHERE relevancia IN ('Alta', 'Media')
             AND resumen IS NOT NULL
             AND fecha_extraccion >= ?
             AND fecha_extraccion <= date(?, '+1 day')
           ORDER BY
             CASE relevancia WHEN 'Alta' THEN 0 ELSE 1 END,
             fecha_extraccion DESC
           LIMIT ?""",
        (fecha_inicio, fecha_fin, LIMITE_NOTICIAS),
    )
    noticias = cursor.fetchall()
    conexion.close()

    if not noticias:
        logger.warning(f"No se encontraron noticias relevantes para la semana {semana_label}.")
        return None

    alta = sum(1 for n in noticias if n[5] == "Alta")
    media = sum(1 for n in noticias if n[5] == "Media")
    logger.info(f"{len(noticias)} noticias ({alta} Alta, {media} Media). Generando informe...")

    paquete = ""
    for i, (diario, titulo, temas, actores, ambito, relevancia, resumen, link) in enumerate(noticias, 1):
        paquete += (
            f"[{i}] [{relevancia}] [{diario}] [{ambito}]\n"
            f"TÍTULO: {titulo}\n"
            f"TEMAS: {temas}\n"
            f"ACTORES: {actores}\n"
            f"RESUMEN: {resumen}\n"
            f"LINK: {link}\n\n"
        )

    prompt = f"""
Sos el asesor estratégico de cabecera de Waldo Wolff. Ya conocés su perfil:
- Legislador de la Ciudad de Buenos Aires, Presidente de la Comisión de Presupuesto, Hacienda y Política Tributaria.
- Cuadro del PRO, jorgemacrista. Referente de la comunidad judía (DAIA, B'nai B'rith). Defensor de la libertad de expresión.
- Misión: blindar la gestión de Jorge Macri, mantener autonomía del PRO frente a LLA, asegurar viabilidad fiscal de la Ciudad.

Esta no es la síntesis de un día. Es el INFORME ESTRATÉGICO DE LA SEMANA {semana_label} ({fecha_inicio} al {fecha_fin}).
Tu tarea: identificar tendencias, movimientos de fondo y líneas estratégicas que emergen de la semana completa.
El tono es de alto secreto: directo, sin grises, como si le hablaras a solas en su despacho.

REGLAS:
1. Cada noticia en UNA SOLA sección. No repetir.
2. No inventes datos ni actores fuera del paquete.
3. Si un eje no tiene noticias relevantes, omitilo.
4. Priorizá análisis de tendencias sobre listado de hechos.

---
ESTRUCTURA DEL INFORME SEMANAL:

1. BALANCE POLÍTICO DE LA SEMANA
Un párrafo ejecutivo. ¿Quién ganó y quién perdió terreno esta semana? ¿El PRO porteño avanzó o retrocedió? ¿Qué movimientos de LLA o del peronismo cambiaron el tablero?

2. TENDENCIAS DE FONDO
Máximo 3. ¿Qué dinámicas estructurales se consolidaron esta semana (más allá de los hechos puntuales)?
Formato: [TENDENCIA] título — análisis en 3-4 líneas.

3. MAPA DE MEDIOS DE LA SEMANA
¿Cómo cubrieron los diarios los temas de Wolff en el acumulado semanal? ¿Hay agenda coordinada? ¿Quién le da espacio, quién ataca?

4. RADAR LEGISLATIVO SEMANAL
Organizá las noticias por eje (omití los que no tengan noticias):
▸ Presupuesto / Coparticipación / Finanzas CABA
▸ PRO vs LLA — disputa territorial y legislativa
▸ Seguridad porteña y política criminal
▸ Servicios e infraestructura porteña
▸ Comunidad judía / DAIA (solo si hay noticias específicas)
▸ Libertad de expresión
▸ Política nacional con impacto en CABA

5. ALERTAS PERMANENTES
Máximo 3. Riesgos que siguen abiertos y requieren seguimiento la semana próxima.
Formato: [ALERTA] título — por qué sigue siendo peligroso.

6. AGENDA ESTRATÉGICA PARA LA PRÓXIMA SEMANA
¿Qué temas conviene instalar o reforzar? ¿Qué movimiento debería anticipar Wolff?
Máximo 2 puntos concretos.

---
NOTICIAS DE LA SEMANA (relevancia Alta primero):
{paquete}
"""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": CTX_BOLETIN,
            "temperature": 0.35,
            "top_p": 0.9,
        },
    }

    try:
        logger.info(f"Iniciando inferencia (num_ctx={CTX_BOLETIN})...")
        t0 = time.time()
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=420)
        respuesta.raise_for_status()
        contenido = respuesta.json()["response"].strip()
        duracion = round(time.time() - t0, 2)
        logger.info(f"Inferencia completada en {duracion}s.")

        carpeta = os.path.join(REPORTES_DIR, semana_label)
        os.makedirs(carpeta, exist_ok=True)
        nombre_archivo = os.path.join(carpeta, f"reporte_semanal_{semana_label}.md")

        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(f"# Informe Estratégico Semanal — {semana_label}\n")
            f.write(f"**Período:** {fecha_inicio} al {fecha_fin}  \n")
            f.write(f"**Noticias analizadas:** {len(noticias)} ({alta} Alta, {media} Media)\n\n")
            f.write("---\n\n")
            f.write(contenido)

        logger.info(f"Reporte guardado en '{nombre_archivo}'.")

        if enviar_telegram:
            from datetime import datetime as dt
            caption = f"📊 Informe Estratégico Semanal — {semana_label}"
            telegram_notifier.enviar_mensaje(
                f"📊 *Informe Estratégico Semanal — {semana_label}*\n"
                f"_{fecha_inicio} al {fecha_fin}_\n"
                f"{len(noticias)} noticias analizadas ({alta} Alta, {media} Media)"
            )
            telegram_notifier.enviar_archivo(nombre_archivo, caption=caption)
            logger.info("Reporte semanal enviado por Telegram.")

        return nombre_archivo

    except Exception as e:
        logger.error(f"Error generando reporte semanal: {e}")
        return None


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Generador de informe estratégico semanal")
    parser.add_argument("--semana", default=None, help="Semana ISO (ej: 2026-W22). Por defecto: semana actual.")
    parser.add_argument("--sin-telegram", action="store_true", help="No enviar por Telegram")
    args = parser.parse_args()
    generar_reporte_semanal(semana_iso=args.semana, enviar_telegram=not args.sin_telegram)
