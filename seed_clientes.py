"""
Pobla la tabla `clientes` con los perfiles configurados.
Correr una vez al configurar un nuevo entorno.

Uso:
    python3 seed_clientes.py
"""
import sqlite3
import logging
from config import DB_PATH, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
from database import inicializar_db
from utils import setup_logging

logger = logging.getLogger(__name__)

WOLFF_PERFIL = """
Waldo Wolff — Legislador de la Ciudad de Buenos Aires (2026).
- Presidente de la Comisión de Presupuesto, Hacienda y Política Tributaria.
- Cuadro del PRO, operador del jorgemacrismo. Responde a Jorge Macri en lo cotidiano y a Mauricio Macri en lo estratégico.
- Ex Ministro de Seguridad porteño. Conoce el presupuesto de la Ciudad (seguridad ~16% del total).
- Referente de la comunidad judía (DAIA, B'nai B'rith). Defensor de la libertad de expresión.
- Misión: blindar la gestión de Jorge Macri, mantener autonomía del PRO frente a La Libertad Avanza,
  asegurar la viabilidad fiscal de la Ciudad (coparticipación, deuda con la Nación).
"""

WOLFF_CRITERIOS_ALTA = (
    "La noticia toca directamente CABA, el PRO, La Libertad Avanza en la Ciudad, "
    "presupuesto/coparticipación porteña, seguridad porteña, DAIA/comunidad judía, "
    "libertad de expresión, o legislatura CABA."
)

WOLFF_CRITERIOS_MEDIA = (
    "Toca política nacional con impacto indirecto en CABA o el PRO "
    "(economía nacional, relación Nación-Ciudad, elecciones 2027)."
)

WOLFF_EJES_RADAR = (
    "Presupuesto / Coparticipación / Finanzas CABA|"
    "PRO vs LLA — disputa territorial y legislativa|"
    "Seguridad porteña y política criminal|"
    "Servicios e infraestructura porteña|"
    "Comunidad judía / DAIA|"
    "Libertad de expresión|"
    "Política nacional con impacto en CABA"
)

WOLFF_PROMPT_BOLETIN = """
Sos el asesor político de cabecera de Waldo Wolff. Conocés en profundidad su posición.
Tu tarea es redactar el "Informe Ejecutivo" con el mapa claro de la semana.
El tono es confidencial, directo, sin vueltas.

REGLAS:
1. Cada noticia aparece en UNA SOLA sección.
2. Si no hay noticias para un eje del Radar, omití ese eje.
3. El eje "Comunidad judía / DAIA" es EXCLUSIVAMENTE para noticias de organizaciones judías, antisemitismo o DAIA.
4. No inventes datos.

ESTRUCTURA:
1. TERMÓMETRO DE LA SEMANA — clima político, impacto en PRO porteño y Jorge Macri
2. MAPA DE MEDIOS — cobertura, sesgos, agenda coordinada contra la gestión porteña
3. RADAR LEGISLATIVO — noticias por eje (omití los sin noticias)
4. ALERTAS DE GESTIÓN — máximo 3: jugadas de LLA, riesgos presupuestarios, crisis para Jorge Macri
5. OPORTUNIDADES — máximo 2: dónde posicionarse desde la Comisión de Presupuesto o sus redes
"""

# Cliente ficticio para pruebas
TEST_PERFIL = """
María González — Diputada Nacional por la Provincia de Santa Fe.
- Bloque UCR. Especialista en temas de salud y educación.
- Presidenta de la Comisión de Salud en Diputados.
- Misión: visibilizar la agenda sanitaria y de educación pública.
"""

TEST_CRITERIOS_ALTA = (
    "La noticia involucra salud pública, educación, sistema universitario, "
    "presupuesto nacional en salud/educación, o política santafesina."
)

TEST_CRITERIOS_MEDIA = (
    "Política nacional con impacto indirecto en salud o educación, "
    "elecciones 2027, UCR, Juntos por el Cambio."
)

CLIENTES = [
    {
        "slug": "wolff",
        "nombre": "Waldo Wolff",
        "perfil": WOLFF_PERFIL,
        "criterios_alta": WOLFF_CRITERIOS_ALTA,
        "criterios_media": WOLFF_CRITERIOS_MEDIA,
        "ejes_radar": WOLFF_EJES_RADAR,
        "prompt_boletin": WOLFF_PROMPT_BOLETIN,
        "telegram_token": TELEGRAM_TOKEN,
        "telegram_chat_id": TELEGRAM_CHAT_ID,
        "activo": 1,
    },
    {
        "slug": "test",
        "nombre": "Cliente Test",
        "perfil": TEST_PERFIL,
        "criterios_alta": TEST_CRITERIOS_ALTA,
        "criterios_media": TEST_CRITERIOS_MEDIA,
        "ejes_radar": "Salud pública|Educación|Política nacional|Santa Fe",
        "prompt_boletin": "Sos asesor de María González. Redactá un informe ejecutivo sobre salud y educación.",
        "telegram_token": "",
        "telegram_chat_id": "",
        "activo": 0,  # inactivo por defecto, activar para pruebas
    },
]


def seed():
    inicializar_db()
    conexion = sqlite3.connect(DB_PATH)

    for cliente in CLIENTES:
        try:
            conexion.execute('''
                INSERT OR IGNORE INTO clientes
                (slug, nombre, perfil, criterios_alta, criterios_media, ejes_radar,
                 prompt_boletin, telegram_token, telegram_chat_id, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                cliente["slug"], cliente["nombre"], cliente["perfil"],
                cliente["criterios_alta"], cliente["criterios_media"],
                cliente["ejes_radar"], cliente["prompt_boletin"],
                cliente["telegram_token"], cliente["telegram_chat_id"],
                cliente["activo"],
            ))
            if conexion.execute("SELECT changes()").fetchone()[0]:
                logger.info(f"Cliente '{cliente['slug']}' insertado.")
            else:
                logger.info(f"Cliente '{cliente['slug']}' ya existía, sin cambios.")
        except Exception as e:
            logger.error(f"Error insertando cliente '{cliente['slug']}': {e}")

    conexion.commit()
    conexion.close()

    # Verificar
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT slug, nombre, activo FROM clientes").fetchall()
    con.close()
    print("\nClientes en la base de datos:")
    for slug, nombre, activo in rows:
        estado = "activo" if activo else "inactivo"
        print(f"  [{estado}] {slug} — {nombre}")


if __name__ == "__main__":
    setup_logging()
    seed()
