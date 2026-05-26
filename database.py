import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def inicializar_db():
    conexion = sqlite3.connect(DB_PATH)
    conexion.execute("PRAGMA journal_mode=WAL;")
    cursor = conexion.cursor()
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diario ON noticias(diario)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_categoria ON noticias(categoria)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fecha_ext ON noticias(fecha_extraccion)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_provincia ON noticias(provincia)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumen ON noticias(resumen)")
    # Migrar columnas nuevas si la tabla ya existía
    for col, tipo in [("ambito", "TEXT"), ("relevancia", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE noticias ADD COLUMN {col} {tipo}")
        except Exception:
            pass  # columna ya existe
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


def guardar_analisis_ia(id_noticia, provincia, temas, actores, resumen, ambito=None, relevancia=None):
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
