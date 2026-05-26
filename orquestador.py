import subprocess
import logging
import concurrent.futures
from utils import setup_logging

logger = logging.getLogger(__name__)

SCRAPERS = [
    "scrapper_infobae.py",
    "scrapper_clarin.py",
    "scrapper_lanacion.py",
    "scrapper_perfil.py",
]


def ejecutar_script(nombre_archivo):
    try:
        result = subprocess.run(["python3", nombre_archivo], capture_output=True, text=True)
        estado = "OK" if result.returncode == 0 else "ERROR"
        logger.info(f"[{estado}] {nombre_archivo}")
        if result.returncode != 0 and result.stderr:
            logger.error(f"  stderr: {result.stderr.strip()[:300]}")
        return result.returncode == 0
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {nombre_archivo}")
        return False


def iniciar_rutina_diaria():
    setup_logging()
    logger.info(f"=== SISTEMA DE INTELIGENCIA DE MEDIOS — {len(SCRAPERS)} scrapers en paralelo ===")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SCRAPERS)) as executor:
        futures = {executor.submit(ejecutar_script, s): s for s in SCRAPERS}
        resultados = {futures[f]: f.result() for f in concurrent.futures.as_completed(futures)}

    exitosos = sum(resultados.values())
    logger.info(f"Fase 1 completada: {exitosos}/{len(SCRAPERS)} scrapers exitosos.")


if __name__ == "__main__":
    iniciar_rutina_diaria()
