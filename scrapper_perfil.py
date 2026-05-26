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


def extraer_datos_noticia_perfil(url):
    try:
        respuesta = get_con_reintentos(url, HEADERS)
        soup = BeautifulSoup(respuesta.text, "html.parser")

        datos = {"bajada": "No encontrada", "autor": "Redacción Perfil", "fecha": "No encontrada", "cuerpo": ""}

        subtitulo = soup.find(['h2', 'p'], class_=re.compile("headline|bajada|copete", re.IGNORECASE))
        if subtitulo:
            datos["bajada"] = subtitulo.get_text(strip=True)

        autor_tag = soup.find(class_=re.compile("author|autor|firma", re.IGNORECASE))
        if autor_tag:
            autor_texto = autor_tag.get_text(strip=True)
            if autor_texto.lower().startswith("por"):
                autor_texto = autor_texto[3:].strip()
            autor_texto = re.sub(r'(Hoy|Ayer)\s+\d{1,2}:\d{2}.*', '', autor_texto, flags=re.IGNORECASE).strip()
            nombres_limpios = re.findall(r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*', autor_texto)
            if nombres_limpios:
                autor_texto = max(nombres_limpios, key=len).strip()
            if not autor_texto or "Perfil" in autor_texto:
                autor_texto = "Redacción Perfil"
            datos["autor"] = autor_texto

        meta_fecha = (soup.find('meta', property='article:published_time') or
                      soup.find('meta', itemprop='datePublished'))
        if meta_fecha and meta_fecha.get('content'):
            datos["fecha"] = meta_fecha.get('content')[:10]
        else:
            fecha_tag = soup.find('time')
            if fecha_tag and fecha_tag.get('datetime'):
                datos["fecha"] = fecha_tag.get('datetime')[:10]

        parrafos = soup.find_all('p')
        texto_completo = ""
        for p in parrafos:
            txt = p.get_text(strip=True)
            if len(txt) > 40:
                texto_completo += txt + "\n\n"

        texto_limpio = texto_completo.strip()
        texto_limpio = re.sub(r'Suscribite a Perfil.*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        datos["cuerpo"] = texto_limpio.strip()
        return datos

    except Exception as e:
        logger.warning(f"Error al extraer {url}: {e}")
        return None


def obtener_titulares_perfil():
    setup_logging()
    database.inicializar_db()

    secciones_config = [
        {"path": "politica", "categoria": "politica"},
        {"path": "economia", "categoria": "economia"},
        {"path": "policia", "categoria": "policiales"},
        {"path": "sociedad", "categoria": "sociedad"},
        {"path": "deportes", "categoria": "deportes"},
    ]

    total_encontradas = 0
    total_guardadas = 0
    logger.info("=== INICIANDO CLIPPING DIARIO DE PERFIL ===")

    for sec in secciones_config:
        url_seccion = (
            "https://442.perfil.com/"
            if sec['path'] == "deportes"
            else f"https://www.perfil.com/seccion/{sec['path']}/"
        )
        logger.info(f"Explorando sección: {sec['categoria'].upper()} -> {url_seccion}")

        try:
            respuesta = get_con_reintentos(url_seccion, HEADERS)
            soup = BeautifulSoup(respuesta.text, "html.parser")
            links_seccion = []

            for articulo in soup.find_all('article', class_=re.compile("news")):
                enlace = articulo.find('a')
                if not enlace:
                    continue
                link = enlace.get('href')
                titulo_tag = articulo.find(['h2', 'h3'], class_=re.compile("title"))
                if link and titulo_tag:
                    titulo = titulo_tag.get_text(strip=True)
                    if link.startswith('/'):
                        link = (f"https://442.perfil.com{link}" if sec['path'] == "deportes"
                                else f"https://www.perfil.com{link}")
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
                datos = extraer_datos_noticia_perfil(link)
                if datos:
                    exito = database.guardar_noticia(
                        diario="Perfil", categoria=sec['categoria'], titulo=titulo,
                        bajada=datos['bajada'], autor=datos['autor'], fecha=datos['fecha'],
                        link=link, cuerpo=datos['cuerpo']
                    )
                    if exito:
                        logger.info(f"  Guardada [{sec['categoria'].upper()}]: {titulo[:50]}")
                        total_guardadas += 1
                time.sleep(1)

        except Exception as e:
            logger.error(f"Error procesando sección {sec['categoria']}: {e}")

    logger.info(f"=== PERFIL: {total_guardadas} nuevas / {total_encontradas} escaneadas ===")


if __name__ == "__main__":
    obtener_titulares_perfil()
