import logging
import os
import time
import requests


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.FileHandler("logs/sintesis.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def get_con_reintentos(url, headers, max_intentos=3, pausa=5, timeout=15):
    logger = logging.getLogger(__name__)
    for intento in range(max_intentos):
        try:
            respuesta = requests.get(url, headers=headers, timeout=timeout)
            respuesta.raise_for_status()
            return respuesta
        except requests.RequestException as e:
            if intento < max_intentos - 1:
                espera = pausa * (intento + 1)
                logger.warning(
                    f"Intento {intento + 1}/{max_intentos} fallido [{url[:60]}]: {e}. "
                    f"Reintentando en {espera}s..."
                )
                time.sleep(espera)
            else:
                raise
