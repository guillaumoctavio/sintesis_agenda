import re
import logging
import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

TELEGRAM_MAX_CHARS = 4000


def _esta_configurado():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram no configurado. Definí TELEGRAM_TOKEN y TELEGRAM_CHAT_ID como variables de entorno.")
        return False
    return True


def _api(metodo, datos=None, archivos=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{metodo}"
    try:
        respuesta = requests.post(url, data=datos, files=archivos, timeout=30)
        respuesta.raise_for_status()
        return respuesta.json()
    except Exception as e:
        logger.error(f"Error llamando a Telegram API ({metodo}): {e}")
        return None


def enviar_mensaje(texto, parse_mode="Markdown"):
    if not _esta_configurado():
        return False
    chunks = [texto[i:i + TELEGRAM_MAX_CHARS] for i in range(0, len(texto), TELEGRAM_MAX_CHARS)]
    for chunk in chunks:
        resultado = _api("sendMessage", datos={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        })
        if not resultado or not resultado.get("ok"):
            # Reintentar sin formato si Telegram rechaza el Markdown
            logger.warning(f"Markdown rechazado, reintentando como texto plano: {resultado}")
            resultado = _api("sendMessage", datos={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            })
            if not resultado or not resultado.get("ok"):
                logger.error(f"Falló envío de mensaje (también sin formato): {resultado}")
                return False
    return True


def enviar_archivo(ruta_archivo, caption=""):
    if not _esta_configurado():
        return False
    try:
        with open(ruta_archivo, "rb") as f:
            resultado = _api("sendDocument", datos={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
            }, archivos={"document": f})
        if not resultado or not resultado.get("ok"):
            logger.error(f"Falló envío de archivo: {resultado}")
            return False
        return True
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {ruta_archivo}")
        return False


def extraer_resumen_boletin(texto_boletin):
    """Extrae termómetro + alertas para el mensaje corto de Telegram."""
    termometro = ""
    alertas = ""

    match_term = re.search(
        r'\*\*TERM[ÓO]METRO[^*]*\*\*\s*\n+(.*?)(?=\n\s*\*\*|\Z)',
        texto_boletin, re.DOTALL | re.IGNORECASE
    )
    if match_term:
        termometro = match_term.group(1).strip()

    match_alert = re.search(
        r'\*\*ALERTAS[^*]*\*\*\s*\n+(.*?)(?=\n\s*\*\*|\Z)',
        texto_boletin, re.DOTALL | re.IGNORECASE
    )
    if match_alert:
        alertas = match_alert.group(1).strip()

    partes = []
    if termometro:
        partes.append(f"TERMÓMETRO\n{termometro}")
    if alertas:
        partes.append(f"ALERTAS\n{alertas}")
    return "\n\n".join(partes)


def notificar_boletin(ruta_archivo, hora_ciclo="", duracion_min=None):
    """Envía resumen por texto + adjunta el archivo .md completo."""
    if not _esta_configurado():
        return

    try:
        with open(ruta_archivo, encoding="utf-8") as f:
            contenido = f.read()
    except FileNotFoundError:
        logger.error(f"No se encontró el boletín: {ruta_archivo}")
        return

    from datetime import datetime
    fecha = datetime.now().strftime("%d/%m/%Y")
    duracion_str = f" · {duracion_min} min" if duracion_min is not None else ""
    encabezado = f"📰 Informe {hora_ciclo} — {fecha}{duracion_str}"

    resumen = extraer_resumen_boletin(contenido)
    mensaje = f"{encabezado}\n\n{resumen}" if resumen else encabezado

    enviar_mensaje(mensaje)
    enviar_archivo(ruta_archivo, caption=f"Informe completo {hora_ciclo} — {fecha}")
    logger.info("Notificación Telegram enviada.")
