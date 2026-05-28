# Arquitectura Cloud Multi-Cliente — Síntesis Agenda

## Contexto y problema a resolver

El sistema actual funciona para un solo cliente (Waldo Wolff) en una máquina local con Ollama + SQLite. El objetivo es escalarlo a múltiples clientes políticos con un pipeline compartido de scraping/análisis objetivo, y análisis personalizado por cliente corriendo en la nube.

El patrón correcto identificado: **dos etapas de análisis**:

- **Stage 1 (compartido):** scraping + análisis objetivo de noticias (se hace una vez para todos los clientes)
- **Stage 2 (por cliente):** re-scoring de relevancia + generación del informe ejecutivo personalizado

---

## Diagnóstico: qué es genérico y qué es cliente-específico

**Genérico (reutilizable sin cambios):**

- Scrapers, `orquestador.py`, `pipeline.py`
- Campos objetivos: `temas`, `actores`, `ambito`, `resumen` en tabla `noticias`

**Cliente-específico (hardcodeado para Wolff hoy):**

- `analisis_ia.py`: campo `relevancia_wolff`, criterios de relevancia, prompt de análisis
- `boletin_ia.py`: prompt ejecutivo con perfil de Wolff, ejes del Radar Legislativo
- `reporte_semanal.py`: mismo patrón
- `informe_cliente.md`: perfil político completo (debe migrar a base de datos)
- `noticias.relevancia`: columna que hoy guarda la relevancia de Wolff (debe ser por cliente)

---

## Arquitectura de dos etapas

```text
STAGE 1 — COMPARTIDO (corre 1 vez para todos los clientes)
───────────────────────────────────────────────────────────
Scrapers → tabla noticias (título, cuerpo, link, fecha)
                  ↓
Análisis objetivo → temas, actores, ámbito, resumen neutro
                  ↓
          tabla `noticias` (sin campo relevancia)


STAGE 2 — POR CLIENTE (corre N veces, una por cliente activo)
───────────────────────────────────────────────────────────────
noticias + perfil_cliente (desde DB)
                  ↓
Scoring relevancia con criterios del cliente
                  ↓
tabla `analisis_clientes` (noticia_id, cliente_id, relevancia, resumen_enfocado)
                  ↓
Generación del boletín con prompt del cliente
                  ↓
tabla `boletines` + Telegram del cliente
```

---

## Schema de base de datos multi-tenant

```sql
CREATE TABLE clientes (
    id               SERIAL PRIMARY KEY,
    slug             TEXT UNIQUE NOT NULL,
    nombre           TEXT NOT NULL,
    perfil           TEXT,
    criterios_alta   TEXT,
    criterios_media  TEXT,
    ejes_radar       TEXT[],
    prompt_boletin   TEXT,
    prompt_semanal   TEXT,
    telegram_token   TEXT,
    telegram_chat_id TEXT,
    activo           BOOLEAN DEFAULT TRUE
);

CREATE TABLE noticias (
    id                SERIAL PRIMARY KEY,
    diario            TEXT,
    titulo            TEXT,
    link              TEXT UNIQUE,
    cuerpo            TEXT,
    fecha_publicacion TEXT,
    fecha_extraccion  TIMESTAMP DEFAULT NOW(),
    temas             TEXT,
    actores           TEXT,
    ambito            TEXT,
    resumen           TEXT
);

CREATE TABLE analisis_clientes (
    id              SERIAL PRIMARY KEY,
    noticia_id      INTEGER REFERENCES noticias(id),
    cliente_id      INTEGER REFERENCES clientes(id),
    relevancia      TEXT,
    resumen_cliente TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(noticia_id, cliente_id)
);

CREATE TABLE boletines (
    id          SERIAL PRIMARY KEY,
    cliente_id  INTEGER REFERENCES clientes(id),
    fecha       DATE,
    tipo        TEXT,
    contenido   TEXT,
    ruta_s3     TEXT,
    enviado     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

## Comparativa de modelos de IA

### Stage 1 — Análisis objetivo (JSON estructurado)

| Modelo | Proveedor | Velocidad | Calidad JSON | Precio input | Precio output | Recomendación |
| --- | --- | --- | --- | --- | --- | --- |
| **Llama 3.1 8B** | Groq | ⚡⚡⚡ 500+ tok/s | ★★★☆ | $0.05/M | $0.08/M | ✅ Ideal Stage 1 |
| **Llama 3.1 70B** | Groq | ⚡⚡ 280 tok/s | ★★★★ | $0.59/M | $0.79/M | Mejor calidad, aún barato |
| **Gemini 2.0 Flash** | Google | ⚡⚡⚡ | ★★★★ | $0.10/M | $0.40/M | Buen balance |
| **GPT-4o Mini** | OpenAI | ⚡⚡ | ★★★★ | $0.15/M | $0.60/M | Más caro que Groq |
| **Claude Haiku 3.5** | Anthropic | ⚡⚡ | ★★★★★ | $0.80/M | $4.00/M | Demasiado caro para Stage 1 |
| **Llama 3.1 local** | Ollama | ⚡ 8 tok/s | ★★★ | $0 | $0 | No escala, GPU cara |

**Veredicto:** Groq con Llama 3.1 8B. Velocísimo, barato, suficiente para extraer JSON estructurado.

### Stage 2 — Boletín ejecutivo (texto largo, razonamiento político)

| Modelo | Proveedor | Calidad análisis | Contexto | Precio input | Precio output | Recomendación |
| --- | --- | --- | --- | --- | --- | --- |
| **Claude Sonnet 4.5** | Anthropic | ★★★★★ | 200K | $3.00/M | $15.00/M | ✅ Ideal Stage 2 premium |
| **GPT-4o** | OpenAI | ★★★★★ | 128K | $2.50/M | $10.00/M | Muy bueno, algo más barato |
| **Gemini 1.5 Pro** | Google | ★★★★ | 1M | $1.25/M | $5.00/M | Bueno, más barato |
| **Claude Haiku 3.5** | Anthropic | ★★★☆ | 200K | $0.80/M | $4.00/M | Menor calidad de análisis |
| **Llama 3.1 70B** | Groq | ★★★★ | 32K | $0.59/M | $0.79/M | Muy barato, calidad aceptable |
| **Gemini 2.0 Flash** | Google | ★★★★ | 1M | $0.10/M | $0.40/M | Sorprendentemente bueno y barato |

**Veredicto:** Claude Sonnet para clientes premium; Gemini 2.0 Flash para escalar con bajo costo.

### Estrategia híbrida recomendada

```text
Stage 1 (análisis objetivo)       → Groq Llama 3.1 8B      ($0.05/M tokens)
Stage 2 scoring relevancia        → Groq Llama 3.1 70B     ($0.59/M tokens)
Stage 2 boletín (cliente base)    → Gemini 2.0 Flash       ($0.10/M tokens)
Stage 2 boletín (cliente premium) → Claude Sonnet 4.5      ($3.00/M tokens)
```

---

## Comparativa de plataformas cloud

### Compute (servidor principal)

| Plataforma | Opción | Specs | Precio/mes | Pros | Contras |
| --- | --- | --- | --- | --- | --- |
| **Hetzner** | CX31 | 4 vCPU, 8GB RAM | €14 (~$15) | Más barato, excelente perf | Sin presencia en LATAM |
| **DigitalOcean** | Droplet 4GB | 2 vCPU, 4GB RAM | $24 | Simple, buen soporte | Más caro que Hetzner |
| **AWS** | t3.medium | 2 vCPU, 4GB RAM | $30 | Ecosistema completo | Complejo, billing impredecible |
| **Google Cloud** | e2-medium | 2 vCPU, 4GB RAM | $24 | Integración Gemini, créditos | Interfaz compleja |
| **Azure** | B2s | 2 vCPU, 4GB RAM | $35 | Bueno para empresas MS | El más caro |
| **Fly.io** | shared-cpu-2x | 2 CPU, 4GB RAM | $20 | Deploy simple con Docker | Menos flexible para cron |

**Recomendación:** Hetzner CX31. Si el cliente exige AWS/GCP por política corporativa → DigitalOcean o GCP.

### Base de datos (PostgreSQL managed)

| Plataforma | Opción | Precio/mes | Pros | Contras |
| --- | --- | --- | --- | --- |
| **Supabase** | Free → Pro | $0 → $25 | Free tier generoso, UI excelente | Límites en free tier |
| **Neon** | Free → Launch | $0 → $19 | Serverless, branching | Menos maduro |
| **DigitalOcean** | Managed PG | $15 | Simple, mismo ecosistema | Más caro que alternativas |
| **AWS RDS** | db.t3.micro | $25 | Enterprise-grade | Complejo, caro |
| **Google Cloud SQL** | db-f1-micro | $15 | Integrado con GCP | Configuración compleja |

**Recomendación:** Supabase (free tier para empezar, $25 cuando escale). Alternativa: Neon.

### Storage de reportes

| Servicio | Precio storage | Precio egress | Pros |
| --- | --- | --- | --- |
| **Cloudflare R2** | $0.015/GB | **$0 egress** | Sin costo de salida — ideal |
| **AWS S3** | $0.023/GB | $0.09/GB | Estándar, confiable |
| **Google Cloud Storage** | $0.020/GB | $0.12/GB | Integrado con GCP |
| **Backblaze B2** | $0.006/GB | $0.01/GB | Más barato, menos ecosistema |
| **DigitalOcean Spaces** | $0.020/GB | $0.01/GB | Simple |

**Recomendación:** Cloudflare R2 — egress gratis es clave para enviar reportes por Telegram.

### Scheduler

| Servicio | Precio | Confiabilidad | Recomendación |
| --- | --- | --- | --- |
| **Cron en VPS** | $0 (incluido) | ★★★★ | ✅ Suficiente para esta escala |
| **GitHub Actions** | Free (2000 min/mes) | ★★★★★ | Bueno para tareas sin estado |
| **GCP Cloud Scheduler** | $0.10/job/mes | ★★★★★ | Confiable, monitoreo nativo |
| **AWS EventBridge** | $1/M eventos | ★★★★★ | Overkill para este caso |

**Recomendación:** Cron en el VPS para empezar. Cloud Scheduler si se necesita observabilidad de jobs.

---

## Estimación de costos por escala

### Asunciones del modelo

- Scrapers: 4 diarios × 3 corridas/día = 300 noticias nuevas/día
- Stage 1: 300 noticias × 800 tokens = 240K tokens/día
- Stage 2 scoring: N clientes × 60 noticias relevantes × 600 tokens
- Stage 2 boletín: N clientes × 3 boletines/día × 15.000 tokens
- Modelo híbrido: Groq 8B para Stage 1, Gemini 2.0 Flash para Stage 2

### Costos fijos (independientes de la cantidad de clientes)

| Concepto | Hetzner stack | DigitalOcean stack | AWS stack |
| --- | --- | --- | --- |
| Compute VPS | €14 ($15) | $24 | $30 |
| PostgreSQL | $25 (Supabase) | $15 (DO managed) | $25 (RDS) |
| Storage R2 | $1 | $1 | $2 (S3) |
| **Base mensual** | **$41** | **$40** | **$57** |

### Costos variables de IA (stack base: Groq + Gemini Flash)

| Clientes | Stage 1 (Groq 8B) | Stage 2 scoring (Groq 70B) | Stage 2 boletín (Gemini Flash) | Total IA/mes | Total + infra |
| --- | --- | --- | --- | --- | --- |
| 5 | $0.40 | $1.50 | $3.60 | $5.50 | $46.50 |
| 10 | $0.40 | $3.00 | $7.20 | $10.60 | $51.60 |
| 20 | $0.40 | $6.00 | $14.40 | $20.80 | $61.80 |
| 50 | $0.40 | $15.00 | $36.00 | $51.40 | $92.40 |

*Stage 1 es fijo porque corre una vez para todos los clientes.*

### Con Claude Sonnet en Stage 2 (clientes premium)

| Clientes | Total IA/mes | Costo/cliente IA | Precio venta sugerido | Margen |
| --- | --- | --- | --- | --- |
| 5 | $37 | $7.40 | $200-500/cliente | >95% |
| 10 | $74 | $7.40 | $200-500/cliente | >95% |
| 20 | $148 | $7.40 | $200-500/cliente | >95% |

---

## Stack recomendado final

```text
┌─────────────────────────────────────────────────────────┐
│  STACK RECOMENDADO PARA ARRANCAR (5-20 clientes)        │
│                                                         │
│  Compute:    Hetzner CX31 — €14/mes                    │
│  Base datos: Supabase PostgreSQL — $0-25/mes            │
│  Storage:    Cloudflare R2 — $1/mes                    │
│  Stage 1 IA: Groq Llama 3.1 8B — $0.05/M tokens       │
│  Stage 2 IA: Claude Sonnet 4.5 — $3/$15 M tokens      │
│  Scheduler:  Cron en VPS                               │
│  Bot:        Python en mismo VPS                       │
│                                                         │
│  Costo base: ~$40/mes + ~$7.40/cliente/mes de IA       │
│  Precio venta sugerido: $150-500/cliente/mes           │
│  Margen: >95%                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Plan de migración en 3 fases

### Fase 1 — Refactor local: separar Stage 1 de Stage 2 (1-2 semanas)

1. Crear tabla `clientes` en SQLite existente con perfil de Wolff extraído del código hardcodeado
2. Separar `analisis_ia.py` → `analisis_objetivo.py` (Stage 1) + `analisis_clientes.py` (Stage 2)
3. Agregar tabla `analisis_clientes` a SQLite
4. Parametrizar prompts de `boletin_ia.py` leyendo de la tabla `clientes`
5. Probar con Wolff + 1 cliente ficticio "test" en local

### Fase 2 — Migrar IA a API (3-5 días)

1. Agregar `groq` y `anthropic` al `requirements.txt`
2. Crear `ai_client.py` con interfaz unificada: `analizar(prompt, modelo)` → soporta Groq, Anthropic, OpenAI
3. `GROQ_API_KEY`, `ANTHROPIC_API_KEY` en variables de entorno
4. Stage 1: llamar a Groq Llama 3.1 8B; Stage 2: llamar a Claude Sonnet
5. Medir costo real con 1 semana de datos antes de migrar infra

### Fase 3 — Deploy cloud (1-2 semanas)

1. Provisionar Hetzner CX31
2. Migrar SQLite → PostgreSQL Supabase (script con `sqlite3` → `psycopg2`)
3. Configurar variables de entorno: `DATABASE_URL`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`
4. Deploy vía `git pull` + `systemd` para bot y pipeline
5. Migrar crontab al servidor
6. Configurar Cloudflare R2 para storage de reportes

---

## Estructura de archivos objetivo

```text
sintesis_agenda/
├── stage1/
│   ├── scrapers/               # sin cambios
│   ├── orquestador.py          # sin cambios
│   └── analisis_objetivo.py    # nuevo: análisis neutro compartido
├── stage2/
│   ├── analisis_clientes.py    # nuevo: scoring de relevancia por cliente
│   ├── boletin_ia.py           # refactorizado: lee config del cliente desde DB
│   └── reporte_semanal.py      # refactorizado: lee config del cliente desde DB
├── core/
│   ├── ai_client.py            # nuevo: interfaz unificada Groq/Anthropic/OpenAI
│   ├── database.py             # migrado a PostgreSQL
│   ├── config.py               # sin cambios estructurales
│   └── utils.py                # sin cambios
├── clientes/
│   └── wolff.json              # perfil como backup/seed de la DB
├── pipeline.py                 # orquesta stage1 + stage2 para cada cliente activo
└── bot_listener.py             # sin cambios estructurales
```
