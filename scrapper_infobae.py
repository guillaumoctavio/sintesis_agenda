import logging
import time
from bs4 import BeautifulSoup
import database
from utils import get_con_reintentos, setup_logging

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def extraer_datos_noticia(url):
    try:
        respuesta = get_con_reintentos(url, HEADERS)
        soup = BeautifulSoup(respuesta.text, "html.parser")

        datos = {"bajada": "", "autor": "", "fecha": "", "cuerpo": ""}

        subtitulo = soup.find('h2')
        if subtitulo:
            datos["bajada"] = subtitulo.get_text(strip=True)

        autor_tag = soup.find(class_=lambda c: c and 'author' in c.lower())
        if autor_tag:
            autor_texto = autor_tag.get_text(strip=True).replace("Seguir en", "")
            if autor_texto.startswith("Por"):
                autor_texto = autor_texto[3:]
            datos["autor"] = autor_texto.strip() or "Redacción"

        meta_fecha = (soup.find('meta', property='article:published_time') or
                      soup.find('meta', itemprop='datePublished'))
        if meta_fecha and meta_fecha.get('content'):
            datos["fecha"] = meta_fecha.get('content')[:10]
        else:
            fecha_tag = soup.find('time') or soup.find(class_=lambda c: c and 'date' in c.lower())
            if fecha_tag:
                fecha_texto = fecha_tag.get_text(strip=True)
                meses = {"Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04", "May": "05", "Jun": "06",
                         "Jul": "07", "Ago": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dic": "12"}
                try:
                    partes = fecha_texto.replace(',', '').split()
                    if len(partes) >= 3:
                        dia = partes[0].zfill(2)
                        mes = meses.get(partes[1][:3], "01")
                        datos["fecha"] = f"{partes[2]}-{mes}-{dia}"
                    else:
                        datos["fecha"] = fecha_texto[:10]
                except Exception:
                    datos["fecha"] = fecha_texto[:10]

        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 20:
                texto_completo += txt + "\n\n"
        datos["cuerpo"] = texto_completo.strip()
        return datos

    except Exception as e:
        logger.warning(f"Error al extraer {url}: {e}")
        return None


def obtener_titulares_infobae():
    setup_logging()
    database.inicializar_db()

    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "sociedad/policiales", "categoria": "policiales"},
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"},
    ]

    total_encontradas = 0
    total_guardadas = 0
    logger.info("=== INICIANDO CLIPPING DIARIO DE INFOBAE ===")

    for sec in secciones_config:
        url_seccion = f"https://www.infobae.com/{sec['path']}/"
        logger.info(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")

        try:
            respuesta = get_con_reintentos(url_seccion, HEADERS)
            soup = BeautifulSoup(respuesta.text, "html.parser")
            links_seccion = []

            for articulo in soup.find_all('a'):
                link = articulo.get('href')
                titulo_h2 = articulo.find('h2')
                if link and titulo_h2:
                    if link.startswith('/'):
                        link = f"https://www.infobae.com{link}"
                    if (f"/{sec['path']}/" in link and "/202" in link and
                            "networking" not in link.lower() and
                            link not in [l[1] for l in links_seccion]):
                        links_seccion.append((titulo_h2.get_text(strip=True), link))

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
                datos = extraer_datos_noticia(link)
                if datos:
                    exito = database.guardar_noticia(
                        diario="Infobae", categoria=sec['categoria'], titulo=titulo,
                        bajada=datos['bajada'], autor=datos['autor'], fecha=datos['fecha'],
                        link=link, cuerpo=datos['cuerpo']
                    )
                    if exito:
                        logger.info(f"  Guardada [{sec['categoria'].upper()}]: {titulo[:50]}")
                        total_guardadas += 1
                time.sleep(1)

        except Exception as e:
            logger.error(f"Error procesando sección {sec['categoria']}: {e}")

    logger.info(f"=== INFOBAE: {total_guardadas} nuevas / {total_encontradas} escaneadas ===")


if __name__ == "__main__":
    obtener_titulares_infobae()
