import requests
from bs4 import BeautifulSoup
import time
import database
import json
import re  # <-- Importado correctamente al principio

def extraer_datos_noticia_clarin(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    
    try:
        respuesta = requests.get(url, headers=headers)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        datos = {"bajada": "No encontrada", "autor": "Redacción", "fecha": "No encontrada", "cuerpo": ""}
        
        # 1. Bajada 
        subtitulo = soup.find('h2') or soup.find(class_=lambda c: c and 'summary' in c.lower())
        if subtitulo: 
            datos["bajada"] = subtitulo.get_text(strip=True)
            
        # 2. Autor (Corregido para evitar "Home" y textos largos)
        autor_tag = soup.find(class_=re.compile("autor|author", re.IGNORECASE))
        if autor_tag: 
            autor_texto = autor_tag.get_text(strip=True)
            
            # Limpiamos el "Por "
            if autor_texto.lower().startswith("por"): 
                autor_texto = autor_texto[3:].strip()
                
            # Filtramos si se cuela el menú o basura larga
            if autor_texto.lower() == "home" or len(autor_texto) > 40:
                autor_texto = "Redacción Clarín"
                
            datos["autor"] = autor_texto or "Redacción Clarín"
            
            # 3. Fecha (Mejorado leyendo Meta Tags)
            # Buscamos en las etiquetas invisibles que leen Facebook y Twitter
        meta_fecha = (soup.find('meta', property='article:published_time') or 
                    soup.find('meta', itemprop='datePublished') or 
                    soup.find('meta', attrs={'name': 'date'}))

        if meta_fecha and meta_fecha.get('content'):
            # Suele venir como "2026-03-17T14:30:00Z", así que cortamos solo los primeros 10 caracteres (YYYY-MM-DD)
            datos["fecha"] = meta_fecha.get('content')[:10] 
        else:
            # Plan B: Buscar etiquetas <time> o clases con 'date'
            fecha_tag = soup.find('time') or soup.find(class_=re.compile("date|fecha", re.IGNORECASE))
            if fecha_tag: 
                datos["fecha"] = fecha_tag.get_text(strip=True)[:15] # Limitamos el largo por si trae basura
        # 4. Cuerpo (Extracción)
        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 30: 
                texto_completo += txt + "\n\n"
                
        # --- LIMPIEZA FINAL DEL TEXTO ---
        texto_limpio = texto_completo.strip()
        
        # Quitamos el aviso de JavaScript
        aviso_js = "Para disfrutar los contenidos de Clarín es necesario que actives JavaScript en tu navegador."
        texto_limpio = texto_limpio.replace(aviso_js, "").strip()
        
        # Quitamos la invitación al newsletter
        aviso_mail = "Recibí en tu mail todas las noticias, historias y análisis de los periodistas de Clarín"
        texto_limpio = texto_limpio.replace(aviso_mail, "").strip()
        
        # Quitamos las firmas de correo y redes sociales
        lineas = texto_limpio.split('\n\n')
        lineas_limpias = [linea for linea in lineas if "@clarin.com" not in linea and not linea.startswith("Redactor")]
        
        datos["cuerpo"] = "\n\n".join(lineas_limpias).strip()
        
        return datos
        
    except Exception as e:
        print(f"  -> Error al extraer {url}: {e}")
        return None

def obtener_titulares_clarin():
    database.inicializar_db() 
    
    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "policiales", "categoria": "policiales"}, 
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"}
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    total_encontradas = 0
    total_guardadas = 0

    print("=== INICIANDO CLIPPING DIARIO DE CLARÍN (MODO JSON) ===\n")

    for sec in secciones_config:
        url_seccion = f"https://www.clarin.com/{sec['path']}/"
        print(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")
        
        try:
            respuesta = requests.get(url_seccion, headers=headers)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            
            links_seccion = []
            
            scripts_json = soup.find_all('script', type='application/ld+json')
            
            for script in scripts_json:
                if script.string and 'ItemList' in script.string:
                    try:
                        data = json.loads(script.string)
                        if 'itemListElement' in data:
                            for item in data['itemListElement']:
                                link = item.get('url', '')
                                titulo = item.get('name', '')
                                
                                # Si es una URL relativa, la convertimos en absoluta
                                if link.startswith('/'):
                                    link = f"https://www.clarin.com{link}"
                                
                                if link and titulo and f"/{sec['path']}/" in link:
                                    if link not in [l[1] for l in links_seccion]:
                                        links_seccion.append((titulo, link))
                    except json.JSONDecodeError:
                        continue
            
            print(f"  -> Encontramos {len(links_seccion)} noticias en {sec['categoria']}.")
            total_encontradas += len(links_seccion)
            
            for titulo, link in links_seccion: 
                
                datos = extraer_datos_noticia_clarin(link)
                
                if datos:
                    exito = database.guardar_noticia(
                        diario="Clarín",
                        categoria=sec['categoria'],
                        titulo=titulo,
                        bajada=datos['bajada'],
                        autor=datos['autor'],
                        fecha=datos['fecha'],
                        link=link,
                        cuerpo=datos['cuerpo']
                    )
                    
                    if exito:
                        print(f"     ✅ Guardada [{sec['categoria'].upper()}]: {titulo[:30]}...")
                        total_guardadas += 1
                    else:
                        print(f"     ⏭️  Ya existía: {titulo[:30]}...")
                
                time.sleep(1.5) 
                
        except Exception as e:
            print(f"Error procesando la sección {sec['categoria']}: {e}")
            
        print("-" * 50)

    print("\n=== REPORTE DE CLIPPING CLARÍN ===")
    print(f"Noticias escaneadas en portadas: {total_encontradas}")
    print(f"Nuevas noticias guardadas en BD: {total_guardadas}")
    print("==================================\n")

if __name__ == "__main__":
    obtener_titulares_clarin()