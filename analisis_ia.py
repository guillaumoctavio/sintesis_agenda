import sqlite3
import requests
import json
import time
import database  # <-- ¡Esta es la línea mágica que faltaba!

# Configuración de tu servidor local de Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.1"

def analizar_noticia_con_ollama(titulo, cuerpo):
    # 1. EL ESCUDO DE TEXTO: Truncamos notas inmensas para no ahogar la GPU
    # 4000 caracteres son aprox 800-1000 tokens. Ideal para extraer datos sin perder contexto.
    texto_limpio = cuerpo[:4000] if cuerpo else ""

    # Este es el "Prompt Maestro". Aquí le damos la personalidad y las reglas estrictas a la IA.
    prompt = f"""
Eres un consultor de redacción argentino de alto nivel.
Lee la siguiente noticia y extrae la información objetiva solicitada. 
Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido, sin texto adicional, ni formato markdown.

Estructura esperada del JSON:
{{
    "temas_clave": ["Etiqueta 1", "Etiqueta 2"], // Conceptos generales (ej. Economía, Inseguridad, Elecciones, Paritarias). Máximo 3.
    "actores_principales": ["Nombre 1", "Institución 1"], // Nombres propios de políticos, jueces, gremios, empresas o países involucrados. Máximo 4.
    "provincia_mencionada": "Provincia argentina principal. Usa 'Nacional' si afecta a todo el país o 'Internacional' si es exterior.",
    "resumen_ejecutivo": "Un resumen directo y al grano de máximo 5 líneas con los hechos duros."
}}

Título de la noticia: {titulo}
Cuerpo de la noticia: {texto_limpio}
""" 

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "format": "json",  # El truco mágico: obliga a Ollama a escupir JSON válido
        "stream": False,   # Queremos la respuesta completa de una vez, no palabra por palabra
        "options": {
            "temperature": 0.1,  # Temperatura bajísima para que no invente cosas y respete el JSON
            "num_ctx": 8192      # Ampliamos la ventana de contexto para que no se pierda al leer
        }
    }

    try:
        # 2. EL BOTÓN DE PÁNICO: timeout=90. Si tarda más de 1 minuto y medio, aborta y sigue.
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=90)
        respuesta.raise_for_status()
        resultado = respuesta.json()
        
        # Extraemos el texto generado por Llama 3.1 y lo convertimos a un diccionario de Python
        datos_json = json.loads(resultado['response'])
        return datos_json
        
    except requests.exceptions.Timeout:
        print(f"     ⚠️  [TIMEOUT] La IA tardó demasiado con esta nota. Saltando...")
        return None
    except json.JSONDecodeError:
        print(f"     ⚠️  [ERROR JSON] La IA no devolvió un formato válido.")
        return None
    except Exception as e:
        print(f"     ❌  [ERROR] Falló el análisis de la IA: {e}")
        return None

def iniciar_analisis_prueba():
    print("=== INICIANDO ANALISTA IA (LLAMA 3.1 LOCAL) ===\n")
    
    conexion = sqlite3.connect('clipping.db')
    cursor = conexion.cursor()
    
    # Buscamos noticias que tengan cuerpo pero que TODAVÍA no hayan sido analizadas por la IA
    # OJO: Dejaste fijada la fecha '2026-03-24'. Si quieres que analice las de hoy, deberías cambiarla o quitar ese filtro.
    cursor.execute("SELECT id, titulo, cuerpo FROM noticias WHERE resumen IS 'Sin resumen' AND fecha_publicacion = '2026-03-24'")
    noticias_pendientes = cursor.fetchall()
    conexion.close()

    if not noticias_pendientes:
        print("No hay noticias pendientes para analizar en esa fecha.")
        return

    print(f"Hay {len(noticias_pendientes)} noticias esperando ser analizadas.\n")

    for id_noticia, titulo, cuerpo in noticias_pendientes:
        print(f"🧠 Analizando noticia #{id_noticia}: {titulo[:50]}...")
        
        analisis = analizar_noticia_con_ollama(titulo, cuerpo)
        
        if analisis:
            # Convertimos las listas de Python (temas y actores) a texto separado por comas para guardarlo en SQL
            temas_texto = ", ".join(analisis.get('temas_clave', []))
            actores_texto = ", ".join(analisis.get('actores_principales', []))
            provincia_texto = analisis.get('provincia_mencionada', 'No especificada')
            resumen_texto = analisis.get('resumen_ejecutivo', 'Sin resumen')

            # ¡Guardamos en la base de datos!
            exito = database.guardar_analisis_ia(id_noticia, provincia_texto, temas_texto, actores_texto, resumen_texto)
            
            if exito:
                print(f"     ✅ Guardado en BD -> 📍 {provincia_texto} | 👤 {actores_texto[:30]}...")
            else:
                print("     ❌ Error al guardar en la BD.")
        else:
            print("     ⏭️  Pasando a la siguiente nota...")
            
        print("-" * 60)
        
        # 3. EL RESPIRO DE LA GPU: Damos 1.5 segundos para que libere VRAM y no se ahogue tu RX 7600
        time.sleep(1.5)

if __name__ == "__main__":
    iniciar_analisis_prueba()