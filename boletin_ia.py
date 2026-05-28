"""
Generador de informe ejecutivo por cliente.

Lee el perfil y prompt del cliente desde la tabla `clientes` en la BD,
y genera el boletín usando las noticias clasificadas en `analisis_clientes`.

Uso:
    python3 boletin_ia.py --cliente wolff --dias 1
"""
import re
import os
import sqlite3
import requests
import time
import argparse
import logging
from datetime import datetime
import database
from config import OLLAMA_URL, MODELO_IA, TEMPERATURA_BOLETIN, CTX_BOLETIN, DB_PATH, REPORTES_DIR
from utils import setup_logging

logger = logging.getLogger(__name__)
LIMITE_NOTICIAS = 50


def limpiar_boletin(texto):
    texto = re.sub(
        r'\*\s+\*\*[^\n]+\*\*\s*\n(?:\s+\*\s+[^\n]*no hay[^\n]*\n?)+',
        '', texto, flags=re.IGNORECASE,
    )
    texto = re.sub(r'\*\s+\*\*[^\n]+\*\*\s*\n(?=\s*\*\s+\*\*|\s*\n|\Z)', '', texto)
    lineas = texto.split('\n')
    vistas = set()
    resultado = []
    for linea in lineas:
        clave = linea.strip()
        if len(clave) > 40:
            if clave in vistas:
                continue
            vistas.add(clave)
        resultado.append(linea)
    texto = '\n'.join(resultado)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def agregar_fuentes(texto, noticias):
    por_diario = {}
    for diario, titulo, ambito, relevancia, resumen, link in noticias:
        if not link:
            continue
        por_diario.setdefault(diario, []).append((relevancia, titulo, link))

    if not por_diario:
        return texto

    lineas = ["\n\n---\n\n**FUENTES**\n"]
    for diario in sorted(por_diario):
        lineas.append(f"\n*{diario}*")
        for relevancia, titulo, link in por_diario[diario]:
            icono = "🔴" if relevancia == "Alta" else "🟡"
            titulo_corto = titulo[:80] + "…" if len(titulo) > 80 else titulo
            lineas.append(f"{icono} [{titulo_corto}]({link})")

    return texto + "\n".join(lineas)


def generar_boletin(slug_cliente="wolff", dias=1):
    cliente = database.obtener_cliente(slug_cliente)
    if not cliente:
        logger.error(f"Cliente '{slug_cliente}' no encontrado en la base de datos.")
        return None

    logger.info(f"=== BOLETÍN: {cliente['nombre'].upper()} — últimos {dias} días ===")

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()

    # Primero intentar desde analisis_clientes (Stage 2 multi-cliente)
    cursor.execute(
        """SELECT n.diario, n.titulo, n.temas, n.actores, n.ambito,
                  ac.relevancia, ac.resumen_cliente, n.link
           FROM analisis_clientes ac
           JOIN noticias n ON n.id = ac.noticia_id
           WHERE ac.cliente_id = ?
             AND ac.relevancia IN ('Alta', 'Media')
             AND ac.resumen_cliente IS NOT NULL
             AND n.fecha_extraccion >= date('now', ?)
           ORDER BY
             CASE ac.relevancia WHEN 'Alta' THEN 0 ELSE 1 END,
             n.fecha_extraccion DESC
           LIMIT ?""",
        (cliente["id"], f"-{dias} days", LIMITE_NOTICIAS),
    )
    noticias = cursor.fetchall()

    # Fallback al campo legacy noticias.relevancia (para el flujo anterior de Wolff)
    if not noticias and slug_cliente == "wolff":
        logger.info("Sin datos en analisis_clientes, usando fallback legacy de noticias.relevancia")
        cursor.execute(
            """SELECT diario, titulo, temas, actores, ambito, relevancia, resumen, link
               FROM noticias
               WHERE relevancia IN ('Alta', 'Media')
                 AND resumen IS NOT NULL
                 AND fecha_extraccion >= date('now', ?)
               ORDER BY
                 CASE relevancia WHEN 'Alta' THEN 0 ELSE 1 END,
                 fecha_extraccion DESC
               LIMIT ?""",
            (f"-{dias} days", LIMITE_NOTICIAS),
        )
        noticias = cursor.fetchall()
    conexion.close()

    if not noticias:
        logger.warning(f"No hay noticias Alta/Media para '{slug_cliente}' en los últimos {dias} días.")
        return None

    alta = sum(1 for n in noticias if n[5] == "Alta")
    media = sum(1 for n in noticias if n[5] == "Media")
    logger.info(f"{len(noticias)} noticias ({alta} Alta, {media} Media). Generando boletín...")

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

    prompt_cliente = cliente.get("prompt_boletin") or ""
    prompt = f"""
{prompt_cliente}

---
REGLAS ESTRICTAS ANTES DE ESCRIBIR:
1. Cada noticia aparece en UNA SOLA sección. Si ya la usaste, no la repitas.
2. Todas las noticias del paquete deben estar mencionadas en algún lugar del informe.
3. Si no hay noticias para un eje, omití ese eje directamente. No escribas "no hay novedades".
4. No inventes datos ni actores.

---
ESTRUCTURA:

1. TERMÓMETRO DE LA SEMANA
Un párrafo sobre el clima político general y cómo impacta al cliente.

2. MAPA DE MEDIOS
Cobertura por diario, sesgos, agenda coordinada.

3. RADAR LEGISLATIVO
Ejes disponibles (omití los sin noticias):
{chr(10).join('▸ ' + eje for eje in (cliente.get('ejes_radar') or '').split('|') if eje.strip())}

Para cada eje: qué pasó, qué medio lo cubrió, qué implica.

4. ALERTAS DE GESTIÓN
Máximo 3. Formato: [ALERTA] título — por qué importa.

5. OPORTUNIDADES DE LA SEMANA
Máximo 2.

---
NOTICIAS (relevancia Alta primero):
{paquete}
"""

    payload = {
        "model": MODELO_IA,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": CTX_BOLETIN, "temperature": TEMPERATURA_BOLETIN, "top_p": 0.9},
    }

    try:
        logger.info(f"Iniciando inferencia (num_ctx={CTX_BOLETIN}, temp={TEMPERATURA_BOLETIN})...")
        t0 = time.time()
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=300)
        respuesta.raise_for_status()

        fuentes_data = [(n[0], n[1], n[4], n[5], n[6], n[7]) for n in noticias]
        boletin_final = limpiar_boletin(respuesta.json()["response"])
        boletin_final = agregar_fuentes(boletin_final, fuentes_data)

        duracion = round(time.time() - t0, 2)
        logger.info(f"Generado en {duracion}s.")

        ahora = datetime.now()
        semana = ahora.strftime("%Y-W%V")
        fecha_hoy = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%Hh")

        carpeta = os.path.join(REPORTES_DIR, semana, slug_cliente)
        os.makedirs(carpeta, exist_ok=True)

        nombre_archivo = os.path.join(carpeta, f"boletin_{fecha_hoy}_{hora}.md")
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(f"# Informe {cliente['nombre']} — {fecha_hoy} {hora}\n\n")
            f.write(boletin_final)
        logger.info(f"Boletín guardado en '{nombre_archivo}'.")
        return nombre_archivo

    except Exception as e:
        logger.error(f"Error al generar boletín para '{slug_cliente}': {e}")
        return None


# Alias backward-compatible para el pipeline existente
def generar_boletin_premium(provincia="Nacional", dias=7):
    return generar_boletin(slug_cliente="wolff", dias=dias)


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Generador de boletín ejecutivo por cliente")
    parser.add_argument("--cliente", default="wolff", help="Slug del cliente (default: wolff)")
    parser.add_argument("--dias", type=int, default=1, help="Ventana de días (default: 1)")
    args = parser.parse_args()
    generar_boletin(slug_cliente=args.cliente, dias=args.dias)
