<div align="center">

# ⚽📊 StatStriker 🤖🎯

### Agente web predictivo de apuestas deportivas basado en **RAG** + **Sistema Experto** + **Búsqueda Semántica**

[![Stars](https://img.shields.io/github/stars/tu-usuario/statstriker?style=for-the-badge&logo=github)](https://github.com/tu-usuario/statstriker/stargazers)
[![Forks](https://img.shields.io/github/forks/tu-usuario/statstriker?style=for-the-badge&logo=github)](https://github.com/tu-usuario/statstriker/network/members)
[![Issues](https://img.shields.io/github/issues/tu-usuario/statstriker?style=for-the-badge)](https://github.com/tu-usuario/statstriker/issues)
[![License](https://img.shields.io/badge/licencia-MIT-green?style=for-the-badge)](#)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20DB-FF6F00?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=flat-square&logo=googlegemini&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white)
![JavaScript](https://img.shields.io/badge/Vanilla%20JS-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

</div>

<a id="top"></a>

<details>
<summary><strong>📑 Tabla de Contenidos</strong></summary>

1. [Acerca del Proyecto](#-acerca-del-proyecto)
2. [Construido con](#-construido-con)
3. [Arquitectura del Sistema](#-arquitectura-del-sistema)
4. [Prerrequisitos](#-prerrequisitos)
5. [Instalación](#-instalación)
6. [Uso y Características](#-uso-y-características)
7. [Pruebas](#-pruebas)
8. [Hoja de Ruta](#-hoja-de-ruta)
9. [Contacto](#-contacto)

</details>

---

## 🧠 Acerca del Proyecto

**StatStriker** es un analista virtual que evalúa propuestas de apuestas de fútbol (p. ej. *"quiero apostar al Real Madrid y más de 2.5 goles"*) usando **solo datos recuperados** de una base de conocimiento vectorial. Se apoya en tres pilares:

| Pilar | Módulo | Descripción |
|---|---|---|
| **1. LLM vía API REST** | `backend/llm_client.py` | Clientes intercambiables **Gemini** / **OpenAI** / **mock** configurados por variables de entorno. |
| **2. Sistema Experto** | `backend/expert_system.py` | Motor de reglas que extrae hechos (mercados, cuotas, perfil de riesgo, señales de juego problemático) e **inyecta dinámicamente** módulos en el *System Prompt*. |
| **3. Búsqueda Semántica** | `backend/vector_store.py` | **ChromaDB** persistente con similitud coseno + *entity linking* de equipos para filtrar por partido. |

> ⚠️ **Aviso:** proyecto educativo con datos simulados. **Nunca** garantiza resultados. +18 · Juega con responsabilidad.

## 🛠️ Construido con

- **Backend:** Python, FastAPI, Uvicorn, Pydantic v2
- **Persistencia:** SQLite (historial) · ChromaDB (vectores)
- **IA:** Google Gemini (`google-genai`) u OpenAI · embeddings locales `all-MiniLM-L6-v2` (ONNX), Gemini u OpenAI
- **Frontend:** HTML5 + CSS3 (*Glassmorphism*) + JavaScript Vanilla (sin dependencias)

## 🏗️ Arquitectura del Sistema

```text
Statstricker/
├── backend/
│   ├── __init__.py
│   ├── config.py          # Settings desde variables de entorno (.env)
│   ├── database.py        # SQLite: historial de consultas
│   ├── embeddings.py      # Proveedores de embeddings (local | gemini | openai)
│   ├── vector_store.py    # PILAR 3 · ChromaDB: upsert + búsqueda semántica
│   ├── expert_system.py   # PILAR 2 · Reglas + System Prompt dinámico
│   ├── llm_client.py      # PILAR 1 · Clientes REST Gemini / OpenAI / mock
│   ├── ingest.py          # Script de ingesta JSON -> embeddings -> ChromaDB
│   └── main.py            # API FastAPI + servidor del frontend
├── data/
│   └── mock_matches.json  # 2 partidos simulados (stats, H2H, lesiones, clima, cuotas)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── storage/               # (generado) chroma_db/ + statstriker.db  — ignorado por git
├── .env.example           # Plantilla de variables (copiar a .env)
├── .gitignore
├── requirements.txt
└── README.md
```

**Flujo RAG de `POST /api/chat`:**

```text
Usuario ──► FastAPI /api/chat
              │
              ├─1─► Sistema Experto: analyze_query()  → mercados, cuotas, riesgo, equipos, alertas
              ├─2─► Embedding de la consulta → ChromaDB.query(top_k, filtro por match_id)
              ├─3─► assess_context_quality() → good | low | none
              ├─4─► build_system_prompt()    → persona + reglas + módulos condicionales
              │     build_user_prompt()      → <contexto> + <historial> + <hechos> + cálculos
              ├─5─► LLM (Gemini / OpenAI) vía API REST
              └─6─► SQLite.save_interaction() → respuesta + reglas activas + fuentes
```

## 📋 Prerrequisitos

- **Python 3.10+** (`python --version` o `py --version` en Windows)
- (Opcional) Una API key de **Google Gemini** ([AI Studio](https://aistudio.google.com/apikey)) u **OpenAI**
- ~100 MB libres (el modelo de embeddings local se descarga la primera vez)

## ⚙️ Instalación

**1. Crear y activar un entorno virtual**

```bash
# Windows (PowerShell)
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

**2. Instalar dependencias**

```bash
pip install -r requirements.txt
```

**3. Configurar variables de entorno** (🔐 las claves **nunca** van en el código)

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Edita `.env` y define, por ejemplo:

```ini
LLM_PROVIDER=gemini        # gemini | openai | mock
GEMINI_API_KEY=tu_clave_aqui
API_SPORTS_KEY=tu_clave_api_football
EMBEDDING_PROVIDER=local   # local | gemini | openai
```

`API_SPORTS_KEY` conecta los marcadores en vivo y el calendario de todas las ligas disponibles en tu plan de API-Football. La clave se usa únicamente en el backend y debe permanecer en `.env`.

> 💡 Sin API key puedes usar `LLM_PROVIDER=mock` para probar ingesta, búsqueda vectorial y reglas del sistema experto.

**4. Inicializar las bases de datos locales (ChromaDB + SQLite)**

```bash
python -m backend.ingest --reset
```

**5. Arrancar el servidor**

```bash
uvicorn backend.main:app --reload --port 8011

# En Windows, si no activaste el entorno virtual (o PowerShell bloquea Activate.ps1):
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8011
```

**6. Abrir la aplicación:** 👉 http://127.0.0.1:8011 · Documentación Swagger: http://127.0.0.1:8011/docs

## 🚀 Uso y Características

- 💬 **Chat Glassmorphism** con sugerencias rápidas, tarjetas de partidos y panel de reglas activas.
- 🧩 **System Prompt dinámico**: módulos por mercado (1X2, Over/Under, BTTS, hándicap, córners, tarjetas), combinada, perfil de riesgo (conservador/moderado/agresivo), Kelly, aviso de garantía, **juego responsable** y calidad del contexto.
- 🧮 **Matemática determinista**: Python calcula probabilidad implícita y cuota combinada; el LLM calcula EV y stake con Kelly fraccional.
- 📎 **Trazabilidad**: cada respuesta muestra fuentes recuperadas y su similitud.
- 🗄️ **Historial persistente** por sesión en SQLite (memoria de los últimos turnos).

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Estado de LLM, ChromaDB y embeddings |
| `GET` | `/api/matches` | Partidos disponibles en la base vectorial |
| `POST` | `/api/chat` | `{ "message": "...", "session_id": "..." }` → análisis RAG |
| `GET` | `/api/history/{session_id}` | Historial de la sesión |
| `DELETE` | `/api/history/{session_id}` | Borra el historial |

## 🧪 Pruebas

**Comprobar el estado:**

```bash
curl http://127.0.0.1:8011/api/health
```

**Consulta RAG desde PowerShell:**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8011/api/chat -Method Post -ContentType "application/json" `
  -Body '{"message":"Quiero apostar al Real Madrid y más de 2.5 goles","session_id":"test"}'
```

**Consulta RAG con curl (macOS / Linux):**

```bash
curl -X POST http://127.0.0.1:8011/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Combinada: gana Liverpool @3.10 y under 2.5 @2.00","session_id":"test"}'
```

**Casos sugeridos para validar el Sistema Experto:**

| Consulta | Reglas esperadas |
|---|---|
| `Quiero apostar al Real Madrid y más de 2.5 goles` | `mercado_1x2`, `mercado_over_under`, `combinada`, `contexto_good` |
| `¿Ambos marcan en el City vs Liverpool? Perfil conservador` | `mercado_btts`, `perfil_conservador` |
| `Dame una apuesta segura al 100% para el Clásico` | `aviso_garantia` |
| `Necesito recuperar lo que perdí con mi sueldo` | `juego_responsable` (stake = 0) |
| `¿Apuesto al Boca Juniors?` | `contexto_low` (equipo no ingerido → responde que no tiene datos) |
| `¿Qué tal el tiempo para cocinar pasta?` | `contexto_none` (sin fragmentos relevantes → no analiza) |

## 🗺️ Hoja de Ruta

- [x] API FastAPI + SQLite
- [x] Ingesta JSON → embeddings → ChromaDB
- [x] Sistema experto con System Prompt dinámico
- [x] Frontend Glassmorphism
- [ ] Respuestas en *streaming* (SSE)
- [ ] Ingesta automática desde una API de datos deportivos real
- [ ] Re-ranking híbrido (BM25 + vectores)
- [ ] Tests automatizados con `pytest` y evaluación RAG
- [ ] Autenticación de usuarios y límites de bankroll

## 📬 Contacto

**Tu Nombre** · [@tu_usuario](https://github.com/tu-usuario) · tu.email@ejemplo.com

Enlace del proyecto: [github.com/tu-usuario/statstriker](https://github.com/tu-usuario/statstriker)

---

<div align="center">

[⬆️ Volver al inicio](#top) · [FastAPI](https://fastapi.tiangolo.com) · [ChromaDB](https://docs.trychroma.com) · [Gemini API](https://ai.google.dev)

</div>
