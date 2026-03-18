import sqlite3
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.1"

def generar_boletin_pba_seguridad():
    print("=== GENERANDO BOLETÍN EJECUTIVO PREMIUM: PBA (SEGURIDAD Y JUSTICIA) ===\n")
    
    conexion = sqlite3.connect('clipping.db')
    cursor = conexion.cursor()
    
    # 1. SOLUCIÓN AL SESGO DE DIARIO: Pedimos 7 de Clarín y 7 de Infobae
    query = """
        SELECT diario, titulo, resumen, link 
        FROM noticias 
        WHERE (provincia LIKE '%Buenos Aires%' OR provincia = 'Nacional' OR provincia = 'La Matanza')
        AND (temas LIKE '%Justicia%' OR temas LIKE '%Inseguridad%')
        AND resumen IS NOT NULL
        AND diario = ?
        ORDER BY fecha_extraccion DESC
        LIMIT 7
    """
    
    cursor.execute(query, ('Clarín',))
    noticias_clarin = cursor.fetchall()
    
    cursor.execute(query, ('Infobae',))
    noticias_infobae = cursor.fetchall()
    
    conexion.close()

    # Juntamos ambos resultados
    noticias_cliente = noticias_clarin + noticias_infobae

    if not noticias_cliente:
        print("No se encontraron noticias que coincidan con el perfil del cliente hoy.")
        return

    print(f"Buscando en la BD... Se encontraron {len(noticias_cliente)} noticias plurales. Procesando síntesis analítica...\n")

    paquete_noticias = ""
    for diario, titulo, resumen, link in noticias_cliente:
        paquete_noticias += f"[{diario}] TÍTULO: {titulo}\nRESUMEN EXACTO: {resumen}\nLINK: {link}\n\n"

    # 2 y 3. SOLUCIÓN AL ANÁLISIS PICANTE: El Nuevo Prompt
    prompt = f"""
Eres el Director de Inteligencia de un Diputado de la Provincia de Buenos Aires.
Analiza el siguiente paquete de noticias de hoy (extraídas de Clarín e Infobae) sobre Inseguridad y Justicia, y redacta un informe confidencial.

Estructura OBLIGATORIA de tu reporte:

1. EL TERMÓMETRO POLÍTICO (Temas Calientes y Línea Editorial):
- Identifica los 2 temas más "picantes" o graves del día.
- Analiza la LÍNEA EDITORIAL de los medios: ¿De qué manera distinta cubren los temas Clarín e Infobae? ¿Alguien está bajando una línea específica contra el gobierno o enfocándose en el morbo? Sé agudo y analítico.

2. DETALLE DE NOTICIAS (Por temática):
Agrupa la información en viñetas por tema (ej. Narcotráfico, Casos Judiciales).
Para cada noticia, NO inventes un resumen genérico, UTILIZA la información provista en el "RESUMEN EXACTO" para dar un contexto completo, mencionando qué diario lo publica.
Debajo de cada viñeta, pega el LINK para que el cliente pueda leer más.

NOTICIAS CRUDAS:
{paquete_noticias}
"""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False 
    }

    try:
        print("⏳ La IA está leyendo las noticias cruzadas y redactando el análisis. Esto tomará unos segundos...\n")
        respuesta = requests.post(OLLAMA_URL, json=payload)
        respuesta.raise_for_status()
        resultado = respuesta.json()
        
        boletin_final = resultado['response']
        print(boletin_final)
        
        with open("boletin_pba_premium.txt", "w", encoding="utf-8") as f:
            f.write(boletin_final)
            print("\n\n[💾 El boletín premium ha sido guardado en 'boletin_pba_premium.txt']")

    except Exception as e:
        print(f"Error al generar el boletín: {e}")

if __name__ == "__main__":
    generar_boletin_pba_seguridad()