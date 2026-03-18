import requests
from bs4 import BeautifulSoup
import time
import database  # <-- ¡Importamos nuestro propio módulo!

def extraer_datos_noticia(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        respuesta = requests.get(url, headers=headers)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, "html.parser")
        
        datos = {"bajada": "", "autor": "", "fecha": "", "cuerpo": ""}
        
        # 1. Bajada
        subtitulo = soup.find('h2')
        if subtitulo: datos["bajada"] = subtitulo.get_text(strip=True)
            
        # 2. Autor
        autor_tag = soup.find(class_=lambda c: c and 'author' in c.lower())
        if autor_tag: 
            autor_texto = autor_tag.get_text(strip=True)
            autor_texto = autor_texto.replace("Seguir en", "")
            if autor_texto.startswith("Por"):
                autor_texto = autor_texto[3:] 
            
            datos["autor"] = autor_texto.strip() or "Redacción"
            
        # 3. Fecha (Normalizada a YYYY-MM-DD)
        meta_fecha = soup.find('meta', property='article:published_time') or soup.find('meta', itemprop='datePublished')
        
        if meta_fecha and meta_fecha.get('content'):
            # Extrae directamente del metadato oculto: "2026-03-17"
            datos["fecha"] = meta_fecha.get('content')[:10]
        else:
            # Plan B: Si no hay metadato, extrae el texto "17 Mar, 2026" y lo traduce
            fecha_tag = soup.find('time') or soup.find(class_=lambda c: c and 'date' in c.lower())
            if fecha_tag: 
                fecha_texto = fecha_tag.get_text(strip=True)
                meses = {"Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04", "May": "05", "Jun": "06", 
                         "Jul": "07", "Ago": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dic": "12"}
                try:
                    partes = fecha_texto.replace(',', '').split() # Separa en ['17', 'Mar', '2026']
                    if len(partes) >= 3:
                        dia = partes[0].zfill(2) # Agrega un 0 si es "5" -> "05"
                        mes_texto = partes[1][:3]
                        mes = meses.get(mes_texto, "01")
                        anio = partes[2]
                        datos["fecha"] = f"{anio}-{mes}-{dia}"
                    else:
                        datos["fecha"] = fecha_texto[:10]
                except:
                    datos["fecha"] = fecha_texto[:10]
        
        # 4. Cuerpo
        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 20: texto_completo += txt + "\n\n"
                
        datos["cuerpo"] = texto_completo.strip()
        return datos
    except Exception as e:
        return None

def obtener_titulares_infobae():
    database.inicializar_db() 
    
    # ORDEN CORREGIDO: Policiales antes que Sociedad
    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "sociedad/policiales", "categoria": "policiales"}, 
        {"path": "sociedad", "categoria": "sociedad"},              
        {"path": "deportes", "categoria": "deportes"}
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    total_encontradas = 0
    total_guardadas = 0

    print("=== INICIANDO CLIPPING DIARIO DE INFOBAE ===\n")

    for sec in secciones_config:
        url_seccion = f"https://www.infobae.com/{sec['path']}/"
        print(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")
        
        try:
            respuesta = requests.get(url_seccion, headers=headers)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            
            articulos = soup.find_all('a')
            links_seccion = []
            
            for articulo in articulos:
                link = articulo.get('href')
                titulo_h2 = articulo.find('h2')
                
                if link and titulo_h2:
                    if link.startswith('/'):
                        link = f"https://www.infobae.com{link}"
                    
                    # FILTRO REFORZADO ubicado en el lugar correcto
                    if (f"/{sec['path']}/" in link and 
                        "/202" in link and 
                        "networking" not in link.lower()):
                        
                        if link not in [l[1] for l in links_seccion]:
                            links_seccion.append((titulo_h2.get_text(strip=True), link))
            
            print(f"  -> Encontramos {len(links_seccion)} noticias en {sec['categoria']}.")
            total_encontradas += len(links_seccion)
            
            # SIN LÍMITE: Procesamos todo el array de links de la sección
            for titulo, link in links_seccion: 
                
                categoria_final = sec['categoria']
                datos = extraer_datos_noticia(link)
                
                if datos:
                    exito = database.guardar_noticia(
                        diario="Infobae",
                        categoria=categoria_final,
                        titulo=titulo,
                        bajada=datos['bajada'],
                        autor=datos['autor'],
                        fecha=datos['fecha'],
                        link=link,
                        cuerpo=datos['cuerpo']
                    )
                    
                    if exito:
                        print(f"     ✅ Guardada [{categoria_final.upper()}]: {titulo[:30]}...")
                        total_guardadas += 1
                    else:
                        print(f"     ⏭️  Ya existía: {titulo[:30]}...")
                
                time.sleep(1) # Pausa amigable con el servidor
                
        except Exception as e:
            print(f"Error procesando la sección {sec['categoria']}: {e}")
            
        print("-" * 50)

    print("\n=== REPORTE DE CLIPPING ===")
    print(f"Noticias escaneadas en portadas: {total_encontradas}")
    print(f"Nuevas noticias guardadas en BD: {total_guardadas}")
    print("===========================\n")

if __name__ == "__main__":
    obtener_titulares_infobae()