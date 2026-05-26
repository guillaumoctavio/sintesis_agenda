import re
import sqlite3
import requests
import time
import argparse
import logging
from datetime import datetime
from config import OLLAMA_URL, MODELO_IA, TEMPERATURA_BOLETIN, CTX_BOLETIN, DB_PATH
from utils import setup_logging

logger = logging.getLogger(__name__)
MODELO = MODELO_IA
LIMITE_NOTICIAS = 50


def limpiar_boletin(texto):
    # 1a. Eliminar subsecciones que solo dicen "no hay noticias"
    texto = re.sub(
        r'\*\s+\*\*[^\n]+\*\*\s*\n(?:\s+\*\s+[^\n]*no hay[^\n]*\n?)+',
        '',
        texto,
        flags=re.IGNORECASE,
    )
    # 1b. Eliminar subsecciones que quedaron vacías (header sin bullets)
    texto = re.sub(
        r'\*\s+\*\*[^\n]+\*\*\s*\n(?=\s*\*\s+\*\*|\s*\n|\Z)',
        '',
        texto,
    )

    # 2. Eliminar bullets duplicados (misma línea en dos secciones distintas)
    lineas = texto.split('\n')
    vistas = set()
    resultado = []
    for linea in lineas:
        clave = linea.strip()
        if len(clave) > 40:  # solo comparar líneas con contenido real
            if clave in vistas:
                continue
            vistas.add(clave)
        resultado.append(linea)

    # 3. Colapsar líneas vacías consecutivas
    texto = '\n'.join(resultado)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def generar_boletin_premium(provincia="Nacional", dias=7):
    logger.info(f"=== GENERANDO BOLETÍN: {provincia.upper()} — últimos {dias} días ===")

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
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
    noticias_cliente = cursor.fetchall()
    conexion.close()

    if not noticias_cliente:
        logger.warning(f"No se encontraron noticias de relevancia Alta/Media en los últimos {dias} días.")
        return

    logger.info(f"{len(noticias_cliente)} noticias disponibles. Empaquetando contexto...")

    paquete_noticias = ""
    for i, (diario, titulo, temas, actores, ambito, relevancia, resumen, link) in enumerate(noticias_cliente, 1):
        paquete_noticias += (
            f"[{i}] [{relevancia}] [{diario}] [{ambito}]\n"
            f"TÍTULO: {titulo}\n"
            f"TEMAS: {temas}\n"
            f"ACTORES: {actores}\n"
            f"RESUMEN: {resumen}\n"
            f"LINK: {link}\n\n"
        )

    prompt = f"""
Sos el asesor político de cabecera de Waldo Wolff. Conocés en profundidad su posición:
- Legislador de la Ciudad de Buenos Aires, Presidente de la Comisión de Presupuesto, Hacienda y Política Tributaria.
- Cuadro del PRO, operador del jorgemacrismo. Responde a Jorge Macri en lo cotidiano y a Mauricio Macri en lo estratégico.
- Ex Ministro de Seguridad porteño. Conoce a fondo el presupuesto de la Ciudad (especialmente seguridad, ~16% del total).
- Referente de la comunidad judía (DAIA, B'nai B'rith). Defensor de la libertad de expresión.
- Su misión política actual: blindar la gestión de Jorge Macri, mantener la autonomía del PRO frente a La Libertad Avanza y asegurar la viabilidad fiscal de la Ciudad (coparticipación, deuda con la Nación).

Tu tarea es leer el paquete de noticias de relevancia Alta y Media, y redactar el "Informe Ejecutivo Semanal" para que Wolff entre a la semana con el mapa claro.
El tono es confidencial, directo, sin vueltas. Nada de relleno. Solo lo que le sirve para tomar decisiones.

---
REGLAS ESTRICTAS ANTES DE ESCRIBIR:
1. Cada noticia aparece en UNA SOLA sección. Si ya la usaste, no la repitas en otra sección.
2. Todas las noticias del paquete deben estar mencionadas en algún lugar del informe. No omitas ninguna.
3. Si no hay noticias para un eje del Radar, omití ese eje directamente. No escribas "no hay novedades".
4. El eje "Comunidad judía / DAIA" es EXCLUSIVAMENTE para noticias que involucren organizaciones judías, antisemitismo, conflicto Israel/Gaza, o declaraciones de la DAIA. NO incluyas casos de violencia genérica o de género aunque ocurran en CABA.
5. No inventes datos ni actores. Solo usá lo que está en las noticias del paquete.

---
ESTRUCTURA:

1. TERMÓMETRO DE LA SEMANA
Un párrafo. ¿El clima político favorece o complica al PRO porteño y a la gestión de Jorge Macri? ¿Hay presión libertaria sobre la Ciudad? ¿Cómo está el humor social en CABA?

2. MAPA DE MEDIOS
¿Cómo cubrieron los diarios los temas que le competen a Wolff esta semana? Señalá sesgos: quién ataca al PRO, quién da espacio, si hay agenda coordinada contra la gestión porteña.

3. RADAR LEGISLATIVO — Lo que le importa esta semana
Organizá TODAS las noticias en los ejes que correspondan (omití los que no tengan noticias):
▸ Presupuesto / Coparticipación / Finanzas CABA
▸ PRO vs LLA — disputa territorial y legislativa
▸ Seguridad porteña y política criminal
▸ Servicios e infraestructura porteña (transporte, energía, obras)
▸ Comunidad judía / DAIA (solo si hay noticias específicas de ese ámbito)
▸ Libertad de expresión
▸ Política nacional con impacto en CABA

Para cada eje: qué pasó, qué medio lo cubrió, qué implica para Wolff + links al final.

4. ALERTAS DE GESTIÓN
Máximo 3. Formato: [ALERTA] título — por qué le importa a Wolff.
Priorizá: jugadas de LLA, riesgos presupuestarios, crisis que afecten a Jorge Macri.

5. OPORTUNIDADES DE LA SEMANA
Máximo 2. ¿Dónde puede posicionarse Wolff o el PRO? ¿Qué tema conviene instalar desde la Comisión de Presupuesto o sus redes?

---
NOTICIAS DE LA SEMANA (relevancia Alta primero):
{paquete_noticias}
"""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": CTX_BOLETIN,
            "temperature": TEMPERATURA_BOLETIN,
            "top_p": 0.9,
        },
    }

    try:
        logger.info(f"Iniciando inferencia Llama 3.1 (num_ctx={CTX_BOLETIN}, temp={TEMPERATURA_BOLETIN})...")
        tiempo_inicio = time.time()

        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=300)
        respuesta.raise_for_status()
        boletin_final = limpiar_boletin(respuesta.json()["response"])

        duracion = round(time.time() - tiempo_inicio, 2)
        logger.info(f"Análisis completado en {duracion}s.")

        print("\n" + "=" * 60)
        print(boletin_final)
        print("=" * 60)

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        nombre_archivo = f"boletin_{provincia.replace(' ', '_')}_{fecha_hoy}.txt"
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(boletin_final)
        logger.info(f"Boletín guardado en '{nombre_archivo}'.")

    except Exception as e:
        logger.error(f"Error al generar el boletín: {e}")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--provincia", default="Nacional", help="Provincia objetivo (default: Nacional)")
    parser.add_argument("--dias", type=int, default=7, help="Rango de días hacia atrás (default: 7)")
    args = parser.parse_args()
    generar_boletin_premium(provincia=args.provincia, dias=args.dias)
