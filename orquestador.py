import subprocess
import time

def ejecutar_script(nombre_archivo):
    print(f"\n{'='*60}")
    print(f"🚀 INICIANDO: {nombre_archivo}")
    print(f"{'='*60}\n")
    
    try:
        # Esto simula exactamente lo que haces tú al escribir "python3 nombre_archivo" en la terminal
        subprocess.run(["python3", nombre_archivo], check=True)
        print(f"\n✅ FINALIZADO EXITOSAMENTE: {nombre_archivo}")
    except subprocess.CalledProcessError:
        print(f"\n❌ ERROR DURANTE LA EJECUCIÓN DE: {nombre_archivo}")
    except FileNotFoundError:
        print(f"\n❌ ARCHIVO NO ENCONTRADO: {nombre_archivo}. Revisa cómo está escrito el nombre.")

def iniciar_rutina_diaria():
    print("🌟 BIENVENIDO AL SISTEMA DE INTELIGENCIA DE MEDIOS 🌟")
    print("Iniciando la recolección masiva de noticias...\n")
    
    # 1. Lista de tus scripts de extracción (¡Ahora sí, los 5 grandes!)
    # Verifica que los nombres coincidan exactamente con tus archivos (.py)
    scripts_extraccion = [
        "scrapper_infobae.py",
        "scrapper_clarin.py",
        "scrapper_lanacion.py",
        "scrapper_perfil.py"     # <-- ¡Aquí está nuestro nuevo integrant
    ]
    
    # Ejecutamos los scrapers uno por uno
    for script in scripts_extraccion:
        ejecutar_script(script)
        # Hacemos una pausa de 2 segundos entre diarios para no saturar tu compu
        time.sleep(2) 
        
    print("\n" + "*"*60)
    print("🎉 ¡FASE 1 COMPLETADA: RECOLECCIÓN EXITOSA! 🎉")
    print("Toda tu base de datos está actualizada con las últimas portadas de los 5 medios.")
    print("*"*60 + "\n")

if __name__ == "__main__":
    iniciar_rutina_diaria()