# 🛡️ Vig-IA: Motor de Triaje Inteligente Type-Safe para Denuncias Policiales

**Vig-IA** es una plataforma de ingeniería de Inteligencia Artificial diseñada para el triaje, clasificación y priorización de denuncias y reportes policiales desestructurados. Combina un microservicio backend **Type-Safe** (FastAPI + Pydantic), razonamiento intermedio **Chain-of-Thought (CoT)**, mitigación activa de **sesgos éticos**, auditoría por oficial de guardia y un dashboard visual interactivo en **Streamlit** (Human-in-the-Loop).

---

## 📋 Problemática y Solución

* **Problemática**: Las comisarías reciben diariamente declaraciones cualitativas e inconsistentes. La falta de estructura dificulta la rápida canalización y existe el riesgo de que la prioridad se vea afectada por sesgos cognitivos o demográficos inferidos en el relato.

* **Solución**: **Vig-IA** procesa la narrativa libre, exige al LLM un desglose analítico imparcial (CoT) e intercepta la respuesta mediante un esquema estricto de Pydantic. El resultado muestra el nivel de urgencia (1 al 5), la unidad de destino y los factores de riesgo en un panel visual donde el oficial de guardia valida o corrige la decisión antes del registro final.

---

## 🚀 Características Principales

1. **Garantía Type-Safe (Pydantic)**: Intercepta alucinaciones de formato o tipos de datos corruptos del modelo, garantizando estabilidad total sin caídas del servidor.

2. **Mitigación Ética de Sesgos**: Prompt de sistema instruido explícitamente para ignorar género, raza, nacionalidad o barrio inferidos al calcular la urgencia.

3. **Razonamiento Transparente (CoT)**: Muestra el proceso analítico paso a paso del modelo antes de la salida JSON final.

4. **Trazabilidad y Auditoría**: Registro obligatorio del Código de Agente para mantener la cadena de custodia en cada expediente.

5. **Arquitectura Híbrida (Local vs. Comercial)**: Soporte para modelos open-source locales mediante **Ollama** (privacidad garantizada) y APIs externas comerciales.

6. **Métricas de Rendimiento**: Monitoreo en tiempo real de latencia (segundos), consumo de tokens y coste estimado en USD.

---

## 🏗️ Estructura del Repositorio

```text
vig-ia/
├── app/
│   ├── __init__.py
│   ├── main.py              # Microservicio FastAPI con endpoints REST
│   ├── config.py            # Configuración de variables globales
│   ├── schemas.py           # Modelos Pydantic Type-Safe (Entrada/Salida/Métricas)
│   ├── prompts.py           # Prompts CoT, Few-shot y reglas éticas antisesgo
│   └── services.py          # Lógica de invocación a Ollama / API externa + Métricas
├── frontend/
│   └── dashboard.py         # Dashboard interactivo en Streamlit (Human-in-the-loop)
├── tests/
│   ├── __init__.py
│   └── test_api.py          # Pruebas unitarias automatizadas con Pytest y Mocking
├── data/
│   └── denuncias.json       # Persistencia local de expedientes confirmados
├── requirements.txt         # Dependencias del proyecto
└── README.md                # Documentación técnica
```

---

## ⚙️ Instalación y Requisitos

1. Clonar el repositorio e instalar dependencias

```bash
git clone https://github.com/GregDev08/Vig-IA.git
cd Vig-IA

# Crear y activar entorno virtual (opcional pero recomendado)
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate

# Instalar librerías
pip install -r requirements.txt
```

---

## 🧪 Ejecución de Pruebas Automatizadas

El proyecto cuenta con cobertura de pruebas unitarias mediante Pytest utilizando mocking para simular las respuestas del LLM:

```bash
pytest -v
```

---

## 🖥️ Modo de Uso y Despliegue en Vivo

Para ejecutar la solución completa, abre dos terminales de forma paralela:

### Paso 1: Iniciar el Backend (FastAPI)

```bash
uvicorn app.main:app --reload
```

Documentación interactiva Swagger disponible en: http://127.0.0.1:8000/docs

### Paso 2: Iniciar el Frontend (Streamlit)

```bash
streamlit run frontend/dashboard.py
```

El dashboard se abrirá automáticamente en tu navegador (http://localhost:8501).

---

## 🛡️ Gobernanza e IA Responsable

- **Modelos Open-Source y Privacidad**: Al utilizar Ollama localmente, los datos sensibles de los ciudadanos jamás abandonan la red del departamento policial.
- **Supervisión Humana (Human-in-the-Loop)**: Ninguna decisión de canalización se toma de forma autónoma; el oficial de guardia mantiene el control final para verificar y confirmar el triaje.

