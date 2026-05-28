import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def inicializar_db():
    conexion = sqlite3.connect(DB_PATH)
    conexion.execute("PRAGMA journal_mode=WAL;")
    cursor = conexion.cursor()

    # Tabla principal de noticias (Stage 1 — datos objetivos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diario TEXT,
            categoria TEXT,
            titulo TEXT,
            bajada TEXT,
            autor TEXT,
            fecha_publicacion TEXT,
            link TEXT UNIQUE,
            cuerpo TEXT,
            fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            provincia TEXT,
            temas TEXT,
            actores TEXT,
            resumen TEXT,
            ambito TEXT,
            relevancia TEXT
        )
    ''')

    # Tabla de clientes (Stage 2 — perfiles por cliente)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            perfil TEXT,
            criterios_alta TEXT,
            criterios_media TEXT,
            ejes_radar TEXT,
            prompt_boletin TEXT,
            prompt_semanal TEXT,
            telegram_token TEXT,
            telegram_chat_id TEXT,
            activo INTEGER DEFAULT 1
        )
    ''')

    # Tabla de análisis por cliente (Stage 2 — relevancia y resumen enfocado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analisis_clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            noticia_id INTEGER REFERENCES noticias(id),
            cliente_id INTEGER REFERENCES clientes(id),
            relevancia TEXT,
            resumen_cliente TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(noticia_id, cliente_id)
        )
    ''')

    # Tabla de boletines generados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boletines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER REFERENCES clientes(id),
            fecha TEXT,
            tipo TEXT,
            contenido TEXT,
            ruta_archivo TEXT,
            enviado INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Índices para noticias
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diario ON noticias(diario)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_categoria ON noticias(categoria)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fecha_ext ON noticias(fecha_extraccion)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_provincia ON noticias(provincia)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumen ON noticias(resumen)")

    # Índices para analisis_clientes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ac_noticia ON analisis_clientes(noticia_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ac_cliente ON analisis_clientes(cliente_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ac_relevancia ON analisis_clientes(relevancia)")

    # Migraciones backward-compatible
    for col, tipo in [("ambito", "TEXT"), ("relevancia", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE noticias ADD COLUMN {col} {tipo}")
        except Exception:
            pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relevancia ON noticias(relevancia)")
    conexion.commit()
    conexion.close()


def link_existe(link):
    conexion = sqlite3.connect(DB_PATH)
    existe = conexion.execute("SELECT 1 FROM noticias WHERE link = ?", (link,)).fetchone() is not None
    conexion.close()
    return existe


def guardar_noticia(diario, categoria, titulo, bajada, autor, fecha, link, cuerpo):
    conexion = sqlite3.connect(DB_PATH)
    insertado = False
    try:
        conexion.execute('''
            INSERT OR IGNORE INTO noticias
            (diario, categoria, titulo, bajada, autor, fecha_publicacion, link, cuerpo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (diario, categoria, titulo, bajada, autor, fecha, link, cuerpo))
        insertado = conexion.execute("SELECT changes()").fetchone()[0] == 1
        conexion.commit()
    except Exception as e:
        logger.error(f"Error al guardar noticia '{link}': {e}")
    finally:
        conexion.close()
    return insertado


def guardar_analisis_objetivo(id_noticia, temas, actores, resumen, ambito):
    """Guarda el análisis neutro de Stage 1 en la tabla noticias."""
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.execute('''
            UPDATE noticias
            SET temas = ?, actores = ?, resumen = ?, ambito = ?, provincia = ?
            WHERE id = ?
        ''', (temas, actores, resumen, ambito, ambito, id_noticia))
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        logger.error(f"Error guardando análisis objetivo para noticia #{id_noticia}: {e}")
        return False


def guardar_analisis_cliente(noticia_id, cliente_id, relevancia, resumen_cliente):
    """Guarda el análisis de Stage 2 en analisis_clientes."""
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.execute('''
            INSERT OR REPLACE INTO analisis_clientes
            (noticia_id, cliente_id, relevancia, resumen_cliente)
            VALUES (?, ?, ?, ?)
        ''', (noticia_id, cliente_id, relevancia, resumen_cliente))
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        logger.error(f"Error guardando análisis cliente #{cliente_id} para noticia #{noticia_id}: {e}")
        return False


def guardar_analisis_ia(id_noticia, provincia, temas, actores, resumen, ambito=None, relevancia=None):
    """Backward-compatible: guarda análisis en noticias (usado por el pipeline legacy de Wolff)."""
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.execute('''
            UPDATE noticias
            SET provincia = ?, temas = ?, actores = ?, resumen = ?, ambito = ?, relevancia = ?
            WHERE id = ?
        ''', (provincia, temas, actores, resumen, ambito, relevancia, id_noticia))
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        logger.error(f"Error guardando análisis IA para noticia #{id_noticia}: {e}")
        return False


def obtener_clientes_activos():
    """Devuelve todos los clientes activos."""
    conexion = sqlite3.connect(DB_PATH)
    rows = conexion.execute(
        "SELECT id, slug, nombre, perfil, criterios_alta, criterios_media, ejes_radar, "
        "prompt_boletin, prompt_semanal, telegram_token, telegram_chat_id FROM clientes WHERE activo = 1"
    ).fetchall()
    conexion.close()
    cols = ["id", "slug", "nombre", "perfil", "criterios_alta", "criterios_media",
            "ejes_radar", "prompt_boletin", "prompt_semanal", "telegram_token", "telegram_chat_id"]
    return [dict(zip(cols, row)) for row in rows]


def obtener_cliente(slug):
    """Devuelve un cliente por slug."""
    conexion = sqlite3.connect(DB_PATH)
    row = conexion.execute(
        "SELECT id, slug, nombre, perfil, criterios_alta, criterios_media, ejes_radar, "
        "prompt_boletin, prompt_semanal, telegram_token, telegram_chat_id FROM clientes WHERE slug = ?",
        (slug,)
    ).fetchone()
    conexion.close()
    if not row:
        return None
    cols = ["id", "slug", "nombre", "perfil", "criterios_alta", "criterios_media",
            "ejes_radar", "prompt_boletin", "prompt_semanal", "telegram_token", "telegram_chat_id"]
    return dict(zip(cols, row))
