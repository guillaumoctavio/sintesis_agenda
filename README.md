# Síntesis Agenda

Sistema de inteligencia de medios político automatizado. Monitorea los principales diarios argentinos, analiza cada noticia con IA local y entrega un informe ejecutivo personalizado por Telegram tres veces por día.

---

## ¿Qué hace?

1. **Recolecta** noticias de Clarín, Infobae, La Nación, Perfil y Página/12 (scraping incremental)
2. **Analiza** cada artículo con Llama 3.1: temas, actores, ámbito y relevancia para el cliente
3. **Genera** un informe ejecutivo estructurado con termómetro político, mapa de medios, radar legislativo, alertas y oportunidades
4. **Entrega** el informe por Telegram con resumen de texto + archivo adjunto

Todo corre localmente. Ningún dato sale de la máquina hacia APIs externas de IA.

---

## Arquitectura

```text
Internet (diarios)
       │
       ▼
┌─────────────────────────────────┐
│  ETAPA 1 — Scrapers (paralelo)  │
│  Clarín · Infobae · La Nación   │
│  Perfil · Página/12             │
└──────────────┬──────────────────┘
               │ SQLite INSERT OR IGNORE
               ▼
┌─────────────────────────────────┐
│  ETAPA 2 — Análisis IA          │
│  Llama 3.1 · noticia por noticia│
│  temas · actores · relevancia   │
└──────────────┬──────────────────┘
               │ SQLite UPDATE
               ▼
┌─────────────────────────────────┐
│  ETAPA 3 — Informe ejecutivo    │
│  50 noticias Alta/Media → IA   │
│  5 secciones + fuentes          │
└──────────────┬──────────────────┘
               │
               ▼
        Telegram (grupo)
```

---

## Estructura del proyecto

```text
sintesis_agenda/
├── pipeline.py              # Orquestador maestro: corre las 3 etapas + Telegram
├── orquestador.py           # Lanza los scrapers en paralelo
├── analisis_ia.py           # Análisis IA noticia por noticia
├── boletin_ia.py            # Generador del informe ejecutivo
├── reporte_semanal.py       # Informe estratégico semanal (a pedido)
├── telegram_notifier.py     # Envío de mensajes y archivos a Telegram
├── bot_listener.py          # Bot con comandos interactivos (/estado, /ayuda)
├── run_bot.sh               # Script de arranque del bot (carga .env_sintesis)
├── database.py              # Gestión SQLite (WAL, índices, migraciones)
├── config.py                # Constantes centralizadas + vars de entorno Telegram
├── utils.py                 # Logging y reintentos compartidos
├── scrapper_clarin.py
├── scrapper_infobae.py
├── scrapper_lanacion.py
├── scrapper_pagina12.py
├── scrapper_perfil.py
├── informe_cliente.md       # Perfil político detallado del cliente
├── .env.example             # Plantilla de credenciales (sin valores reales)
├── requirements.txt
└── reportes/                # Informes generados (gitignoreado)
    └── YYYY-WXX/
        ├── boletin_YYYY-MM-DD_HHh.md
        └── reporte_semanal_YYYY-WXX.md
```

---

## Instalación

### 1. Clonar y crear entorno virtual

```bash
git clone git@github.com:guillaumoctavio/sintesis_agenda.git
cd sintesis_agenda
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Instalar Ollama y el modelo

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1
```

### 3. Configurar credenciales de Telegram

```bash
cp .env.example ~/.env_sintesis
nano ~/.env_sintesis          # completar TOKEN y CHAT_ID
source ~/.env_sintesis
echo 'source ~/.env_sintesis' >> ~/.bashrc
```

Para obtener el token: hablar con **@BotFather** en Telegram → `/newbot`.  
Para obtener el chat_id: mandar un mensaje al bot y consultar `getUpdates`.

### 4. Configurar el cron (ejecución automática)

```bash
crontab -e
```

Agregar:

```
0 5  * * * . /home/TU_USUARIO/.env_sintesis && cd /ruta/al/proyecto && /usr/bin/python3 pipeline.py --dias 1 >> logs/cron.log 2>&1
0 13 * * * . /home/TU_USUARIO/.env_sintesis && cd /ruta/al/proyecto && /usr/bin/python3 pipeline.py --dias 1 >> logs/cron.log 2>&1
0 22 * * * . /home/TU_USUARIO/.env_sintesis && cd /ruta/al/proyecto && /usr/bin/python3 pipeline.py --dias 1 >> logs/cron.log 2>&1
```

### 5. Iniciar el bot de Telegram

```bash
# Como servicio de usuario (systemd)
systemctl --user enable sintesis-bot.service
systemctl --user start sintesis-bot.service

# O manualmente en background
nohup bash run_bot.sh >> logs/bot.log 2>&1 &
```

---

## Uso manual

```bash
# Pipeline completo (scraping + análisis + boletín + Telegram)
python3 pipeline.py --dias 1

# Solo etapas individuales
python3 orquestador.py
python3 analisis_ia.py --dias 7
python3 boletin_ia.py --dias 7

# Informe estratégico semanal
python3 reporte_semanal.py
python3 reporte_semanal.py --semana 2026-W22
python3 reporte_semanal.py --sin-telegram   # solo guardar
```

---

## Bot de Telegram — comandos

| Comando | Acción |
| --- | --- |
| `/start` | Bienvenida |
| `/estado` | Estadísticas de la BD y estado del sistema |
| `/ayuda` | Lista de comandos |

Los informes automáticos llegan al grupo configurado a las **05h, 13h y 22h**.  
Cada mensaje incluye el resumen (termómetro + alertas) y el archivo `.md` adjunto con el informe completo y las fuentes linkeadas.

---

## Informe ejecutivo — estructura

1. **Termómetro de la semana** — clima político general y su impacto en el cliente
2. **Mapa de medios** — cobertura por diario, sesgos y agenda coordinada
3. **Radar Legislativo** — noticias organizadas por eje temático
4. **Alertas de gestión** — máximo 3, priorizadas por urgencia
5. **Oportunidades** — dónde posicionarse esta semana
6. **Fuentes** — todos los links, agrupados por diario con indicador 🔴/🟡

---

## Personalización por cliente

El sistema se adapta a cualquier perfil. La configuración del cliente vive en:

- `informe_cliente.md` — perfil político detallado
- `analisis_ia.py` — criterios de relevancia (Alta/Media/Baja)
- `boletin_ia.py` — prompt del informe ejecutivo

Actualmente configurado para **Waldo Wolff** (Legislador CABA, Presidente Comisión de Presupuesto, PRO).

---

## Requisitos

- Python 3.12+
- [Ollama](https://ollama.com) con modelo `llama3.1`
- GPU recomendada: 8 GB VRAM · RAM: 16 GB mínimo
- Bot de Telegram configurado

---

## Notas técnicas

- **Scraping incremental:** si encuentra 3 URLs consecutivas ya almacenadas, asume que la sección está al día y para.
- **Reintentos:** cada request HTTP reintenta hasta 3 veces con backoff exponencial.
- **Análisis solo de nuevos:** el analizador detecta artículos sin resumen y los procesa; no reprocesa lo ya analizado.
- **Página/12:** usa JavaScript; el cuerpo no está disponible en HTML estático. Se usa el `og:description` como fallback.
- **Validación de IA:** el JSON devuelto por el modelo se valida contra un esquema estricto; si falla, la noticia se marca `Omitido` para no reintentar indefinidamente.

---

*Uso privado. Todos los derechos reservados.*
