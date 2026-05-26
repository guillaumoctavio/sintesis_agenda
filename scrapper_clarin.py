import logging
import time
import json
import re
from bs4 import BeautifulSoup
import database
from utils import get_con_reintentos, setup_logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9"
}


def extraer_datos_noticia_clarin(url):
    try:
        respuesta = get_con_reintentos(url, HEADERS)
        soup = BeautifulSoup(respuesta.text, "html.parser")

        datos = {"bajada": "No encontrada", "autor": "Redacción", "fecha": "No encontrada", "cuerpo": ""}

        subtitulo = soup.find('h2') or soup.find(class_=lambda c: c and 'summary' in c.lower())
        if subtitulo:
            datos["bajada"] = subtitulo.get_text(strip=True)

        autor_tag = soup.find(class_=re.compile("autor|author", re.IGNORECASE))
        if autor_tag:
            autor_texto = autor_tag.get_text(strip=True)
            if autor_texto.lower().startswith("por"):
                autor_texto = autor_texto[3:].strip()
            if autor_texto.lower() == "home" or len(autor_texto) > 40:
                autor_texto = "Redacción Clarín"
            datos["autor"] = autor_texto or "Redacción Clarín"

        meta_fecha = (soup.find('meta', property='article:published_time') or
                      soup.find('meta', itemprop='datePublished') or
                      soup.find('meta', attrs={'name': 'date'}))
        if meta_fecha and meta_fecha.get('content'):
            datos["fecha"] = meta_fecha.get('content')[:10]
        else:
            fecha_tag = soup.find('time') or soup.find(class_=re.compile("date|fecha", re.IGNORECASE))
            if fecha_tag:
                datos["fecha"] = fecha_tag.get_text(strip=True)[:15]

        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 30:
                texto_completo += txt + "\n\n"

        texto_limpio = texto_completo.strip()
        texto_limpio = texto_limpio.replace(
            "Para disfrutar los contenidos de Clarín es necesario que actives JavaScript en tu navegador.", ""
        ).strip()
        texto_limpio = texto_limpio.replace(
            "Recibí en tu mail todas las noticias, historias y análisis de los periodistas de Clarín", ""
        ).strip()
        lineas = texto_limpio.split('\n\n')
        lineas_limpias = [l for l in lineas if "@clarin.com" not in l and not l.startswith("Redactor")]
        datos["cuerpo"] = "\n\n".join(lineas_limpias).strip()
        return datos

    except Exception as e:
        logger.warning(f"Error al extraer {url}: {e}")
        return None


def obtener_titulares_clarin():
    setup_logging()
    database.inicializar_db()

    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "policiales", "categoria": "policiales"},
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"},
    ]

    total_encontradas = 0
    total_guardadas = 0
    logger.info("=== INICIANDO CLIPPING DIARIO DE CLARÍN ===")

    for sec in secciones_config:
        url_seccion = f"https://www.clarin.com/{sec['path']}/"
        logger.info(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")

        try:
            respuesta = get_con_reintentos(url_seccion, HEADERS)
            soup = BeautifulSoup(respuesta.text, "html.parser")
            links_seccion = []

            for script in soup.find_all('script', type='application/ld+json'):
                if script.string and 'ItemList' in script.string:
                    try:
                        data = json.loads(script.string)
                        if 'itemListElement' in data:
                            for item in data['itemListElement']:
                                link = item.get('url', '')
                                titulo = item.get('name', '')
                                if link.startswith('/'):
                                    link = f"https://www.clarin.com{link}"
                                if link and titulo and f"/{sec['path']}/" in link:
                                    if link not in [l[1] for l in links_seccion]:
                                        links_seccion.append((titulo, link))
                    except json.JSONDecodeError:
                        continue

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
                datos = extraer_datos_noticia_clarin(link)
                if datos:
                    exito = database.guardar_noticia(
                        diario="Clarín", categoria=sec['categoria'], titulo=titulo,
                        bajada=datos['bajada'], autor=datos['autor'], fecha=datos['fecha'],
                        link=link, cuerpo=datos['cuerpo']
                    )
                    if exito:
                        logger.info(f"  Guardada [{sec['categoria'].upper()}]: {titulo[:50]}")
                        total_guardadas += 1
                time.sleep(1.5)

        except Exception as e:
            logger.error(f"Error procesando sección {sec['categoria']}: {e}")

    logger.info(f"=== CLARÍN: {total_guardadas} nuevas / {total_encontradas} escaneadas ===")


if __name__ == "__main__":
    obtener_titulares_clarin()
