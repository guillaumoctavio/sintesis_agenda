import requests

# 1. Definimos la URL exacta del endpoint
url = "https://resultados.mininterior.gob.ar/api/resultados/getResultados"

# 2. Configuramos los parámetros de nuestra búsqueda
parametros = {
    "anioEleccion": "2025",
    "tipoRecuento": "1", # Provisorio
    "tipoEleccion": "2", # Generales
    "categoriaId": "2",  # Diputados
    "distritoId": "1"    # CABA
}

# 3. Hacemos la consulta a la API
print("Consultando a la DINE...")
try:
    respuesta = requests.get(url, params=parametros)
    respuesta.raise_for_status() # Lanza error si la página no responde bien
    
    # 4. Convertimos la respuesta a formato JSON (diccionario de Python)
    datos = respuesta.json()
    
    # 5. Extraemos e imprimimos la información que nos interesa
    print("\n--- RESULTADOS ---")
    print(f"Mesas escrutadas: {datos.get('mesasTotalizadasPorcentaje', 0)}%")
    print(f"Votantes totales: {datos.get('cantidadVotantes', 0)}")
    
    # Los resultados de las agrupaciones políticas vienen en una lista
    agrupaciones = datos.get('valoresTotalizadosPositivos', [])
    
    print("\nVotos por Agrupación:")
    for partido in agrupaciones:
        nombre = partido.get('nombreAgrupacion')
        votos = partido.get('votos')
        porcentaje = partido.get('votosPorcentaje')
        print(f"- {nombre}: {votos} votos ({porcentaje}%)")

except requests.exceptions.RequestException as e:
    print(f"Hubo un error al conectarse con la API: {e}")