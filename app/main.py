import json
import os
from typing import Any, Dict, Union

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import DenunciaComparativaOutput, DenunciaInput, DenunciaOutput
from app.services import procesar_triaje_denuncia

app = FastAPI(
    title="Vig-IA API - Motor de Triaje Policial Type-Safe",
    description=(
        "Microservicio REST de triaje inteligente de denuncias policiales con validación estricta "
        "Type-Safe vía Pydantic, mitigación de sesgos éticos e identificación de agentes."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORIAL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "denuncias.json")


def _asegurar_directorio_data():
    """Crea el directorio data/ y el archivo json inicializado si no existe o está vacío."""
    os.makedirs(os.path.dirname(HISTORIAL_FILE), exist_ok=True)
    if not os.path.exists(HISTORIAL_FILE) or os.path.getsize(HISTORIAL_FILE) == 0:
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


@app.get("/", tags=["Healthcheck"])
def root():
    """Endpoint de estado para verificación del microservicio."""
    return {
        "status": "ok",
        "servicio": "Vig-IA API Engine",
        "version": "1.0.0",
        "documentacion": "/docs",
    }


@app.post(
    "/api/v1/triaje",
    response_model=Union[DenunciaOutput, DenunciaComparativaOutput],
    status_code=status.HTTP_200_OK,
    tags=["Triaje"],
)
def ejecutar_triaje_denuncia(datos: DenunciaInput):
    """Endpoint principal para procesar una denuncia. Soporta triaje simple y comparativo dual."""
    try:
        resultado = procesar_triaje_denuncia(datos)
        return resultado
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error de Type-Safety: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando el triaje: {str(e)}",
        )


@app.post(
    "/api/v1/guardar-denuncia",
    status_code=status.HTTP_201_CREATED,
    tags=["Historial"],
)
def guardar_denuncia_confirmada(denuncia: Dict[str, Any]):
    """Guarda una denuncia canalizada y confirmada por el oficial humano en el histórico local."""
    try:
        _asegurar_directorio_data()
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except (json.JSONDecodeError, Exception):
            historial = []

        historial.append(denuncia)

        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

        return {"status": "success", "mensaje": "Denuncia canalizada y registrada exitosamente en Vig-IA."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando la denuncia: {str(e)}",
        )


@app.patch("/api/v1/denuncias/{indice}/estado", tags=["Historial"])
def actualizar_estado_denuncia(indice: int, estado: Dict[str, str]):
    """Actualiza manualmente el estado de un expediente desde el dashboard."""
    estados_validos = {"En revisión", "Canalizado"}
    nuevo_estado = estado.get("estado")
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=400, detail="Estado no válido.")

    try:
        _asegurar_directorio_data()
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            historial = json.load(f)
        if indice < 0 or indice >= len(historial):
            raise HTTPException(status_code=404, detail="Expediente no encontrado.")

        historial[indice]["estado_expediente"] = nuevo_estado
        if "resolucion_final" in estado:
            historial[indice]["resolucion_final"] = estado["resolucion_final"]
        if "observaciones_operador" in estado:
            historial[indice]["observaciones_operador"] = estado["observaciones_operador"]

        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
        return {
            "status": "success",
            "estado_expediente": nuevo_estado,
            "resolucion_final": historial[indice].get("resolucion_final"),
            "observaciones_operador": historial[indice].get("observaciones_operador"),
        }
    except HTTPException:
        raise
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando el expediente: {str(e)}")


@app.get("/api/v1/denuncias", tags=["Historial"])
def obtener_denuncias_guardadas():
    """Devuelve el historial de denuncias registradas para el panel de control."""
    try:
        _asegurar_directorio_data()
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except (json.JSONDecodeError, Exception):
            historial = []

        return {"total": len(historial), "denuncias": historial}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error leyendo el historial: {str(e)}",
        )