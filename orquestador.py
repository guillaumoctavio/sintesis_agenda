import sqlite3
import requests
import time
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.1"

# --- CONFIGURACIÓN OPTIMIZADA PARA RX 7600 8GB + 32GB RAM ---
PROVINCIA_OBJETIVO = "Nacional" 
LIMITE_NOTICIAS = 30 # Tu hardware se banca esto sin problemas
CARACTERES_POR_NOTA = 1200 # Unos 300 tokens por nota. 30 notas = 9.000 tokens. ¡Entra perfecto en la memoria ampliada!

def generar_boletin_premium():
    print(f"=== GENERANDO REPORTE DE INTELIGENCIA ESTRATÉGICA: {PROVINCIA_OBJETIVO.upper()} ===\n")
    
    conexion = sqlite3.connect('clipping.db')
    cursor = conexion.cursor()
    
    # 1. BÚSQUEDA MULTIMEDIOS
    query = f"""
        SELECT diario, titulo, resumen, link, cuerpo 
        FROM noticias 
        WHERE (provincia LIKE '%{PROVINCIA_OBJETIVO}%' OR provincia = 'Nacional')
        AND resumen IS NOT NULL
        ORDER BY fecha_extraccion DESC
        LIMIT ?
    """
    
    cursor.execute(query, (LIMITE_NOTICIAS,))
    noticias_cliente = cursor.fetchall()
    conexion.close()

    if not noticias_cliente:
        print(f"No se encontraron noticias recientes relevantes para {PROVINCIA_OBJETIVO}.")
        return

    print(f"🔎 Se extrajeron {len(noticias_cliente)} noticias con texto completo. Empaquetando datos...\n")

    # 2. EMPAQUETADO DEL CONTEXTO
    paquete_noticias = ""
    for diario, titulo, resumen, link, cuerpo in noticias_cliente:
        
        # Truncamos inteligentemente a 1200 caracteres para mantener el foco en la línea editorial
        cuerpo_recortado = cuerpo[:CARACTERES_POR_NOTA] + "... [Continúa]" if cuerpo and len(cuerpo) > CARACTERES_POR_NOTA else cuerpo
        
        paquete_noticias += f"[{diario}] TÍTULO: {titulo}\nRESUMEN: {resumen}\nTEXTO EDITORIAL: {cuerpo_recortado}\nLINK: {link}\n\n"

    # 3. EL SÚPER-PROMPT DE INTELIGENCIA
    prompt = f"""
Eres el Director de Inteligencia Estratégica y Análisis de Medios de un importante Senador de {PROVINCIA_OBJETIVO}.
Tu tarea es leer el paquete de noticias adjunto (que incluye medios como Página/12, La Nación, Clarín, Perfil e Infobae) y redactar un "Boletín Ejecutivo de Situación".

El tono debe ser estrictamente profesional, agudo, objetivo y confidencial.

ESTRUCTURA OBLIGATORIA DEL INFORME:

1. SÍNTESIS EJECUTIVA:
- Un párrafo inicial que resuma el "humor social y político" del día basándote en la gravedad, el tono de los titulares y el TEXTO EDITORIAL de las noticias.

2. EL MAPA DE MEDIOS (Análisis de Línea Editorial):
- Compara cómo están tratando la información los distintos diarios analizando sus TEXTOS EDITORIALES. 
- ¿Hay un sesgo evidente? (Por ejemplo, ¿Página/12 usa adjetivos negativos mientras La Nación justifica? ¿Alguien omite datos clave?). Busca contradicciones o enfoques distintos sobre un mismo tema.

3. DESGLOSE DE EJES CLAVE (Agrupación temática):
- Agrupa las noticias en viñetas por tema principal (Ej: Economía, Conflictos Políticos, Casos Judiciales).
- Para cada viñeta, redacta una síntesis completa utilizando la información del "RESUMEN" y los detalles del "TEXTO EDITORIAL". No inventes datos. Menciona siempre qué medio publicó qué enfoque.
- AL FINAL DE CADA VIÑETA, debes pegar los LINKS EXACTOS correspondientes para que el Senador pueda ampliar la lectura.

4. ALERTAS DE GESTIÓN (Recomendación Estratégica):
- Basado en este panorama y el sesgo de los medios de hoy, dale a tu jefe 2 recomendaciones breves sobre qué temas debe evitar y qué temas presentan una oportunidad política para él.

---
NOTICIAS CRUDAS DEL DÍA:
{paquete_noticias}
"""

    # 4. CONFIGURACIÓN DEL PAYLOAD CON OVERCLOCKING CEREBRAL
    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 16384,     # ¡AQUÍ ESTÁ LA MAGIA! Le damos a Llama 3.1 una memoria a corto plazo inmensa (16k tokens)
            "temperature": 0.3,   # Bajamos la temperatura para que sea más analítico y menos "creativo/poético"
            "top_p": 0.9          # Enfoca las respuestas en los conceptos más lógicos
        }
    }

    try:
        print("🤖 INICIANDO INFERENCIA LLAMA 3.1")
        print("⚙️  Parámetros: num_ctx=16384, temperature=0.3")
        print("⏳ La GPU Radeon RX 7600 está procesando el sesgo editorial de los 5 medios...")
        
        tiempo_inicio = time.time() # Iniciamos el cronómetro
        
        respuesta = requests.post(OLLAMA_URL, json=payload)
        respuesta.raise_for_status()
        resultado = respuesta.json()
        
        tiempo_fin = time.time() # Detenemos el cronómetro
        duracion = round(tiempo_fin - tiempo_inicio, 2)
        
        boletin_final = resultado['response']
        print(f"\n✅ ¡Análisis completado en {duracion} segundos!\n")
        print("="*60)
        print(boletin_final)
        print("="*60)
        
        # Guardamos el archivo con la fecha de hoy
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        nombre_archivo = f"boletin_{PROVINCIA_OBJETIVO.replace(' ', '_')}_{fecha_hoy}.txt"
        
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(boletin_final)
            print(f"\n[💾 El informe de inteligencia ha sido guardado en '{nombre_archivo}']")

    except Exception as e:
        print(f"Error al generar el boletín: {e}")

if __name__ == "__main__":
    generar_boletin_premium()