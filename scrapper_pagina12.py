import logging
import time
import re
from bs4 import BeautifulSoup
import database
from utils import get_con_reintentos, setup_logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9"
}


def extraer_datos_noticia_pagina12(url):
    try:
        respuesta = get_con_reintentos(url, HEADERS)
        soup = BeautifulSoup(respuesta.text, "html.parser")

        datos = {"bajada": "No encontrada", "autor": "Redacción Página/12", "fecha": "No encontrada", "cuerpo": ""}

        subtitulo = soup.find('p', class_='lead') or soup.find('h3', class_=re.compile("p12Heading", re.IGNORECASE))
        if subtitulo:
            datos["bajada"] = subtitulo.get_text(strip=True)

        autor_tag = soup.find(class_=re.compile("author-name", re.IGNORECASE))
        if autor_tag:
            autor_texto = autor_tag.get_text(strip=True)
            if autor_texto.lower().startswith("por"):
                autor_texto = autor_texto[3:].strip()
            datos["autor"] = autor_texto or "Redacción Página/12"

        fecha_tag = soup.find('time')
        if fecha_tag and fecha_tag.get('datetime'):
            datos["fecha"] = fecha_tag.get('datetime')[:10]

        # Plan A: contenedor article-body (requiere JS — normalmente vacío)
        cuerpo_contenedor = soup.find(class_=lambda c: c and 'article-body' in c.lower())
        if cuerpo_contenedor:
            parrafos = cuerpo_contenedor.find_all('p')
        else:
            parrafos = soup.find_all('p', class_=re.compile('paragraph'))

        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 25:
                texto_completo += txt + "\n\n"

        texto_limpio = texto_completo.strip()
        texto_limpio = re.sub(r'Defendé la otra mirada.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        texto_limpio = re.sub(r'Si llegaste hasta acá.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        texto_limpio = re.sub(r'Todos los derechos reservados.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        texto_limpio = texto_limpio.strip()

        # Plan B: Página/12 renderiza el cuerpo vía JS; usar og:description como fallback
        if not texto_limpio:
            meta_desc = (soup.find('meta', property='og:description') or
                         soup.find('meta', attrs={'name': 'description'}))
            if meta_desc and meta_desc.get('content'):
                texto_limpio = meta_desc.get('content')
                logger.debug(f"Usando og:description como cuerpo para {url}")

        datos["cuerpo"] = texto_limpio
        return datos

    except Exception as e:
        logger.warning(f"Error al extraer {url}: {e}")
        return None


def obtener_titulares_pagina12():
    setup_logging()
    database.inicializar_db()

    secciones_config = [
        {"path": "el-pais", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"},
    ]

    total_encontradas = 0
    total_guardadas = 0
    logger.info("=== INICIANDO CLIPPING DIARIO DE PÁGINA/12 ===")

    for sec in secciones_config:
        url_seccion = f"https://www.pagina12.com.ar/secciones/{sec['path']}/"
        logger.info(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")

        try:
            respuesta = get_con_reintentos(url_seccion, HEADERS)
            soup = BeautifulSoup(respuesta.text, "html.parser")
            links_seccion = []

            for enlace in soup.find_all('a'):
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

            logger.info(f"  -> Encontramos {len(links_seccion)} noticias en {sec['categoria']}.")
            total_encontradas += len(links_seccion)

            consecutivos = 0
            for titulo, link in links_seccion:
                if database.link_existe(link):
                    consecutivos += 1
                    if consecutivos >= 3:
                        logger.info(f"  -> Sección {sec['categoria']} al día, deteniendo.")
                        break
                    continue
                consecutivos = 0
                datos = extraer_datos_noticia_pagina12(link)
                if datos:
                    exito = database.guardar_noticia(
                        diario="Página/12", categoria=sec['categoria'], titulo=titulo,
                        bajada=datos['bajada'], autor=datos['autor'], fecha=datos['fecha'],
                        link=link, cuerpo=datos['cuerpo']
                    )
                    if exito:
                        logger.info(f"  Guardada [{sec['categoria'].upper()}]: {titulo[:50]}")
                        total_guardadas += 1
                else:
                    logger.warning(f"  Nota sin cuerpo o bloqueada: {link}")
                time.sleep(1)

        except Exception as e:
            logger.error(f"Error procesando sección {sec['categoria']}: {e}")

    logger.info(f"=== PÁGINA/12: {total_guardadas} nuevas / {total_encontradas} escaneadas ===")


if __name__ == "__main__":
    obtener_titulares_pagina12()
