import requests
from bs4 import BeautifulSoup
import time
import database
import re

def extraer_datos_noticia_perfil(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    
    try:
        respuesta = requests.get(url, headers=headers)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        datos = {"bajada": "No encontrada", "autor": "Redacción Perfil", "fecha": "No encontrada", "cuerpo": ""}
        
        # 1. Bajada (Perfil suele usar h2 o p con clase 'headline' o 'bajada')
        subtitulo = soup.find(['h2', 'p'], class_=re.compile("headline|bajada|copete", re.IGNORECASE))
        if subtitulo: 
            datos["bajada"] = subtitulo.get_text(strip=True)
            
     # 2. Autor (Limpieza Ultra-Avanzada para Perfil)
        autor_tag = soup.find(class_=re.compile("author|autor|firma", re.IGNORECASE))
        if autor_tag: 
            autor_texto = autor_tag.get_text(strip=True)
            
            # 1. Le quitamos el "Por " si lo tiene al principio
            if autor_texto.lower().startswith("por"): 
                autor_texto = autor_texto[3:].strip()
                
            # 2. Eliminamos todo lo que empiece con "Hoy " o "Ayer " y una hora (ej: "Hoy 19:51")
            autor_texto = re.sub(r'(Hoy|Ayer)\s+\d{1,2}:\d{2}.*', '', autor_texto, flags=re.IGNORECASE).strip()
            
            # 3. Limpiamos repeticiones raras de nombres/redes sociales (ej: Andy Ferreyraandyferreyra...)
            # Buscamos mayúsculas seguidas de minúsculas para rescatar solo el Nombre y Apellido real.
            nombres_limpios = re.findall(r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*', autor_texto)
            if nombres_limpios:
                # Nos quedamos con la coincidencia más larga, que suele ser el nombre real
                autor_texto = max(nombres_limpios, key=len).strip()
                
            # 4. Si después de limpiar quedó vacío o dice "Perfil", le ponemos "Redacción Perfil"
            if not autor_texto or "Perfil" in autor_texto:
                autor_texto = "Redacción Perfil"
                
            datos["autor"] = autor_texto
            
        # 3. Fecha (Normalizada a YYYY-MM-DD usando meta tags)
        meta_fecha = (soup.find('meta', property='article:published_time') or 
                      soup.find('meta', itemprop='datePublished'))
                      
        if meta_fecha and meta_fecha.get('content'):
            datos["fecha"] = meta_fecha.get('content')[:10]
        else:
            fecha_tag = soup.find('time')
            if fecha_tag and fecha_tag.get('datetime'): 
                datos["fecha"] = fecha_tag.get('datetime')[:10]
            
        # 4. Cuerpo de la noticia
        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 40: 
                texto_completo += txt + "\n\n"
                
        # Limpieza final específica de Perfil (por si hay carteles de suscripción)
        texto_limpio = texto_completo.strip()
        texto_limpio = re.sub(r'Suscribite a Perfil.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        
        datos["cuerpo"] = texto_limpio.strip()
        return datos
        
    except Exception as e:
        print(f"  -> Error al extraer {url}: {e}")
        return None

def obtener_titulares_perfil():
    database.inicializar_db() 
    
    # Secciones de Perfil
    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "policia", "categoria": "policiales"}, # Perfil usa "policia"
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"}
    ]
    
    # Algunas secciones de deportes en Perfil redirigen a "442.perfil.com"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    total_encontradas = 0
    total_guardadas = 0

    print("=== INICIANDO CLIPPING DIARIO DE PERFIL ===\n")

    for sec in secciones_config:
        # Lógica especial para deportes que usa el subdominio 442
        if sec['path'] == "deportes":
            url_seccion = "https://442.perfil.com/"
        else:
            url_seccion = f"https://www.perfil.com/seccion/{sec['path']}/"
            
        print(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")
        
        try:
            respuesta = requests.get(url_seccion, headers=headers)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            
            # Perfil encierra sus notas en <article class="news...">
            articulos = soup.find_all('article', class_=re.compile("news"))
            links_seccion = []
            
            for articulo in articulos:
                enlace = articulo.find('a')
                if not enlace:
                    continue
                    
                link = enlace.get('href')
                titulo_tag = articulo.find(['h2', 'h3'], class_=re.compile("title"))
                
                if link and titulo_tag:
                    titulo = titulo_tag.get_text(strip=True)
                    
                    if link.startswith('/'):
                        if sec['path'] == "deportes":
                            link = f"https://442.perfil.com{link}"
                        else:
                            link = f"https://www.perfil.com{link}"
                    
                    if link not in [l[1] for l in links_seccion]:
                        links_seccion.append((titulo, link))
            
            print(f"  -> Encontramos {len(links_seccion)} noticias en {sec['categoria']}.")
            total_encontradas += len(links_seccion)
            
            # Procesamos todas las noticias encontradas
            for titulo, link in links_seccion: 
                
                datos = extraer_datos_noticia_perfil(link)
                
                if datos:
                    exito = database.guardar_noticia(
                        diario="Perfil",
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

    print("\n=== REPORTE DE CLIPPING PERFIL ===")
    print(f"Noticias escaneadas en portadas: {total_encontradas}")
    print(f"Nuevas noticias guardadas en BD: {total_guardadas}")
    print("==================================\n")

if __name__ == "__main__":
    obtener_titulares_perfil()