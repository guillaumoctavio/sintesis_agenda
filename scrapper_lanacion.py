import requests
from bs4 import BeautifulSoup
import time
import database
import re

def extraer_datos_noticia_lanacion(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    
    try:
        respuesta = requests.get(url, headers=headers)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        datos = {"bajada": "No encontrada", "autor": "Redacción La Nación", "fecha": "No encontrada", "cuerpo": ""}
        
        # 1. Bajada
        subtitulo = soup.find(['h2', 'h3'], class_=re.compile("subhead|bajada|resumen", re.IGNORECASE))
        if subtitulo: 
            datos["bajada"] = subtitulo.get_text(strip=True)
            
   # 2. Autor (Limpieza Avanzada)
        autor_tag = soup.find(class_=re.compile("author|autor|firma|marquee", re.IGNORECASE))
        if autor_tag: 
            autor_texto = autor_tag.get_text(strip=True)
            
            # Limpiezas específicas de los vicios de La Nación
            autor_texto = re.sub(r'Escuchar\s*Nota', '', autor_texto, flags=re.IGNORECASE)
            autor_texto = re.sub(r'^LA NACION', '', autor_texto, flags=re.IGNORECASE)
            autor_texto = re.sub(r'^Por\s+', '', autor_texto, flags=re.IGNORECASE)
            
            # Si es un vivo con 20 autores pegados
            if "Autores en vivo" in autor_texto:
                autor_texto = "Cobertura Conjunta"
                
            datos["autor"] = autor_texto.strip() or "Redacción La Nación"
            
        # 3. Fecha (Se mantiene igual...)
        meta_fecha = soup.find('meta', property='article:published_time')
        if meta_fecha and meta_fecha.get('content'):
            datos["fecha"] = meta_fecha.get('content')[:10]
        else:
            fecha_tag = soup.find('time')
            if fecha_tag and fecha_tag.get('datetime'): 
                datos["fecha"] = fecha_tag.get('datetime')[:10]
            
        # 4. Cuerpo de la noticia (Con limpieza de Copyright)
        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 40: 
                texto_completo += txt + "\n\n"
                
        # --- LIMPIEZA FINAL DEL TEXTO DE LA NACIÓN ---
        texto_limpio = texto_completo.strip()
        
        # Borramos todo desde donde dice "© Copyright" hasta el final
        texto_limpio = re.sub(r'© Copyright.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        # Por las dudas, borramos el cartel de reCAPTCHA si quedó suelto
        texto_limpio = re.sub(r'Protegido por reCAPTCHA.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        
        datos["cuerpo"] = texto_limpio.strip()
        return datos
        
    except Exception as e:
        print(f"  -> Error al extraer {url}: {e}")
        return None

def obtener_titulares_lanacion():
    database.inicializar_db() 
    
    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "seguridad", "categoria": "policiales"}, 
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"}
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    total_encontradas = 0
    total_guardadas = 0

    print("=== INICIANDO CLIPPING DIARIO DE LA NACION ===\n")

    for sec in secciones_config:
        url_seccion = f"https://www.lanacion.com.ar/{sec['path']}/"
        print(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")
        
        try:
            respuesta = requests.get(url_seccion, headers=headers)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            
            enlaces = soup.find_all('a')
            links_seccion = []
            
            for enlace in enlaces:
                link = enlace.get('href')
                titulo_tag = enlace.find(['h1', 'h2', 'h3']) or enlace
                titulo = titulo_tag.get_text(strip=True)
                
                if link and titulo:
                    if link.startswith('/'):
                        link = f"https://www.lanacion.com.ar{link}"
                    
                    if f"/{sec['path']}/" in link and "-nid" in link.lower() and link not in [l[1] for l in links_seccion]:
                        links_seccion.append((titulo, link))
            
            print(f"  -> Encontramos {len(links_seccion)} noticias en {sec['categoria']}.")
            total_encontradas += len(links_seccion)
            
            for titulo, link in links_seccion: 
                
                datos = extraer_datos_noticia_lanacion(link)
                
                if datos:
                    exito = database.guardar_noticia(
                        diario="La Nación",
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
                
                time.sleep(1) 
                
        except Exception as e:
            print(f"Error procesando la sección {sec['categoria']}: {e}")
            
        print("-" * 50)

    print("\n=== REPORTE DE CLIPPING LA NACION ===")
    print(f"Noticias escaneadas en portadas: {total_encontradas}")
    print(f"Nuevas noticias guardadas en BD: {total_guardadas}")
    print("=====================================\n")

if __name__ == "__main__":
    obtener_titulares_lanacion()