import sqlite3

def inicializar_db():
    """Crea la base de datos y la tabla si no existen."""
    conexion = sqlite3.connect('clipping.db')
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
            fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conexion.commit()
    conexion.close()

def guardar_noticia(diario, categoria, titulo, bajada, autor, fecha, link, cuerpo):
    """Guarda una noticia y devuelve True si es nueva, False si ya existía."""
    conexion = sqlite3.connect('clipping.db')
    cursor = conexion.cursor()
    insertado = False
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO noticias 
            (diario, categoria, titulo, bajada, autor, fecha_publicacion, link, cuerpo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (diario, categoria, titulo, bajada, autor, fecha, link, cuerpo))
        
        if cursor.rowcount == 1:
            insertado = True
        conexion.commit()
    except Exception as e:
        print(f"  [DB] ❌ Error al guardar en BD: {e}")
    finally:
        conexion.close()
    return insertado

def guardar_analisis_ia(id_noticia, provincia, temas, actores, resumen):
    try:
        conexion = sqlite3.connect('clipping.db')
        cursor = conexion.cursor()
        
        cursor.execute('''
            UPDATE noticias 
            SET provincia = ?, temas = ?, actores = ?, resumen = ?
            WHERE id = ?
        ''', (provincia, temas, actores, resumen, id_noticia))
        
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        print(f"Error guardando en BD: {e}")
        return False