import requests
from bs4 import BeautifulSoup
import time
import database
import re

def extraer_datos_noticia_pagina12(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    
    try:
        respuesta = requests.get(url, headers=headers)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        datos = {"bajada": "No encontrada", "autor": "Redacción Página/12", "fecha": "No encontrada", "cuerpo": ""}
        
        # 1. Bajada 
        subtitulo = soup.find('p', class_='lead') or soup.find('h3', class_=re.compile("p12Heading", re.IGNORECASE))
        if subtitulo: 
            datos["bajada"] = subtitulo.get_text(strip=True)
            
        # 2. Autor 
        autor_tag = soup.find(class_=re.compile("author-name", re.IGNORECASE))
        if autor_tag: 
            autor_texto = autor_tag.get_text(strip=True)
            if autor_texto.lower().startswith("por"): 
                autor_texto = autor_texto[3:].strip()
            datos["autor"] = autor_texto or "Redacción Página/12"
            
        # 3. Fecha 
        fecha_tag = soup.find('time')
        if fecha_tag and fecha_tag.get('datetime'): 
            datos["fecha"] = fecha_tag.get('datetime')[:10]
            
        # 4. Cuerpo de la noticia (MÁS FLEXIBLE)
        texto_completo = ""
        
        # PLAN A: Buscamos el contenedor principal
        cuerpo_contenedor = soup.find(class_=lambda c: c and 'article-body' in c.lower())
        
        if cuerpo_contenedor:
            parrafos = cuerpo_contenedor.find_all('p')
        else:
            # PLAN B: Si no encuentra el contenedor, agarra todos los párrafos de la nota
            parrafos = soup.find_all('p', class_=re.compile('paragraph'))
            
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 25: 
                texto_completo += txt + "\n\n"
                    
        # Limpieza final
        texto_limpio = texto_completo.strip()
        texto_limpio = re.sub(r'Defendé la otra mirada.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        texto_limpio = re.sub(r'Si llegaste hasta acá.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        
        datos["cuerpo"] = texto_limpio.strip()
        return datos
        
    except Exception as e:
        print(f"  -> Error al extraer {url}: {e}")
        return None

def obtener_titulares_pagina12():
    database.inicializar_db() 
    
    secciones_config = [
        {"path": "el-pais", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"}
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    total_encontradas = 0
    total_guardadas = 0

    print("=== INICIANDO CLIPPING DIARIO DE PÁGINA/12 ===\n")

    for sec in secciones_config:
        url_seccion = f"https://www.pagina12.com.ar/secciones/{sec['path']}/"
        print(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")
        
        try:
            respuesta = requests.get(url_seccion, headers=headers)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            
            enlaces = soup.find_all('a')
            links_seccion = []
            
            for enlace in enlaces:
                link = enlace.get('href')
                if not link:
                    continue
                
                if re.search(r'/\d{4}/\d{2}/\d{2}/', link):
                    titulo_tag = enlace.find(['h2', 'h3', 'h4'])
                    titulo = titulo_tag.get_text(strip=True) if titulo_tag else enlace.get_text(strip=True)
                    
                    if len(titulo) > 15:
                        if link.startswith('/'):
                            link = f"https://www.pagina12.com.ar{link}"
                        
                        if link not in [l[1] for l in links_seccion]:
                            links_seccion.append((titulo, link))
            
            print(f"  -> Encontramos {len(links_seccion)} noticias en {sec['categoria']}.")
            total_encontradas += len(links_seccion)
            
            for titulo, link in links_seccion: 
                datos = extraer_datos_noticia_pagina12(link)
                
                if datos and datos['cuerpo']: 
                    exito = database.guardar_noticia(
                        diario="Página/12",
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
                else:
                    # Este es nuestro "botón de pánico" visual para saber qué está fallando
                    print(f"     ⚠️  Nota sin cuerpo o bloqueada: {link}")
                
                time.sleep(1)
                
        except Exception as e:
            print(f"Error procesando la sección {sec['categoria']}: {e}")
            
        print("-" * 50)

    print("\n=== REPORTE DE CLIPPING PÁGINA/12 ===")
    print(f"Noticias escaneadas en portadas: {total_encontradas}")
    print(f"Nuevas noticias guardadas en BD: {total_guardadas}")
    print("=====================================\n")

if __name__ == "__main__":
    obtener_titulares_pagina12()