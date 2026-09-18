"""
Batería de Pruebas Unitarias para Vig-IA (Pytest).
Evalúa la API, validación Type-Safe y manejo de errores mediante Mocking.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DenunciaOutput, MetricasPeticion

client = TestClient(app)


def test_healthcheck():
    """Prueba 1: Verificar que el endpoint de estado/bienvenida responda adecuadamente."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "Vig-IA API" in response.json()["servicio"]


@patch("app.main.procesar_triaje_denuncia")
def test_triaje_exitoso_mock(mock_procesar):
    """
    Prueba 2: Evaluar la respuesta exitosa del endpoint /api/v1/triaje 
    simulando (mocking) una salida válida del servicio LLM.
    """
    # Configuración de la respuesta simulada respetando el esquema Type-Safe
    mock_salida = DenunciaOutput(
        codigo_agente="POL-98765",
        razonamiento_cot="Hechos: Robo a mano armada. Prioridad 4 asignada por peligro físico inminente.",
        categoria="Robo con violencia",
        nivel_urgencia=4,
        resumen_10_palabras="Robo a mano armada en la vía pública.",
        departamento_asignado="Unidad de Robos con Violencia",
        factores_riesgo=["Arma de fuego", "Violencia física"],
        metricas=MetricasPeticion(
            tokens_entrada=120,
            tokens_salida=90,
            latencia_segundos=1.25,
            coste_estimado_usd=0.0
        )
    )
    mock_procesar.return_value = mock_salida

    payload = {
        "codigo_agente": "POL-98765",
        "texto_denuncia": "Un sujeto me encañonó con una pistola para quitarme el reloj en el parque.",
        "proveedor": "ollama",
        "modelo": "qwen2.5:7b"
    }

    response = client.post("/api/v1/triaje", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["codigo_agente"] == "POL-98765"
    assert data["nivel_urgencia"] == 4
    assert data["departamento_asignado"] == "Unidad de Robos con Violencia"
    assert "Arma de fuego" in data["factores_riesgo"]


@patch("app.main.procesar_triaje_denuncia")
def test_triaje_fallo_typesafety_mock(mock_procesar):
    """
    Prueba 3: Evaluar el manejo controlado de errores cuando el LLM sufre 
    una alucinación estructural (ValueError atrapado por Pydantic/Type-Safety).
    """
    # Simulamos que la validación de Pydantic o el JSON corrupto lanzó un ValueError
    mock_procesar.side_effect = ValueError("El modelo generó un JSON sin el campo 'nivel_urgencia'.")

    payload = {
        "codigo_agente": "POL-98765",
        "texto_denuncia": "Texto corto probando error de estructura...",
        "proveedor": "ollama",
        "modelo": "qwen2.5:7b"
    }

    response = client.post("/api/v1/triaje", json=payload)
    
    # Debe devolver un HTTP 422 Unprocessable Entity controlado sin colapsar la API
    assert response.status_code == 422
    assert "Error de Type-Safety" in response.json()["detail"]


@patch("app.main.procesar_triaje_denuncia")
def test_triaje_dual_mock(mock_procesar):
    """Prueba 4: verificar que la respuesta dual conserva los resultados locales y externos."""
    mock_local = DenunciaOutput(
        codigo_agente="POL-98765",
        razonamiento_cot="Hechos locales",
        categoria="Robo",
        nivel_urgencia=3,
        resumen_10_palabras="Robo menor con riesgo",
        departamento_asignado="Unidad de Robos",
        factores_riesgo=["Violencia"],
        metricas=MetricasPeticion(
            tokens_entrada=10,
            tokens_salida=8,
            latencia_segundos=1.0,
            coste_estimado_usd=0.0
        )
    )
    mock_externo = DenunciaOutput(
        codigo_agente="POL-98765",
        razonamiento_cot="Hechos externos",
        categoria="Robo con violencia",
        nivel_urgencia=4,
        resumen_10_palabras="Robo con violencia",
        departamento_asignado="Unidad de Robos con Violencia",
        factores_riesgo=["Arma"],
        metricas=MetricasPeticion(
            tokens_entrada=12,
            tokens_salida=9,
            latencia_segundos=0.9,
            coste_estimado_usd=0.0005
        )
    )
    mock_procesar.return_value = {"resultado_local": mock_local.model_dump(), "resultado_externo": mock_externo.model_dump()}

    payload = {
        "codigo_agente": "POL-98765",
        "texto_denuncia": "Texto suficientemente largo para ejecutar el triaje dual........",
        "proveedor": "groq",
        "modelo": "llama-3.3-70b-versatile",
        "dual": True
    }

    response = client.post("/api/v1/triaje", json=payload)

    assert response.status_code == 200
    assert "resultado_local" in response.json()
    assert "resultado_externo" in response.json()
    assert response.json()["resultado_local"]["categoria"] == "Robo"


def test_guardar_y_recuperar_denuncia():
    """Prueba 5: Verificar la persistencia e historial de denuncias canalizadas."""
    expediente_test = {
        "codigo_agente": "POL-11111",
        "categoria": "Test Vandalismo",
        "nivel_urgencia": 2,
        "departamento_asignado": "Seguridad Ciudadana",
        "resumen_10_palabras": "Prueba de guardado automático."
    }

    # Guardar denuncia
    resp_guardar = client.post("/api/v1/guardar-denuncia", json=expediente_test)
    assert resp_guardar.status_code == 201

    # Obtener historial
    resp_historial = client.get("/api/v1/denuncias")
    assert resp_historial.status_code == 200
    assert resp_historial.json()["total"] >= 1


def test_actualizar_estado_con_resolucion_operador():
    """Prueba 6: ver que el cierre del caso registra la resolución y las observaciones del oficial."""
    expediente_test = {
        "codigo_agente": "POL-22222",
        "categoria": "Test Robo",
        "nivel_urgencia": 3,
        "departamento_asignado": "Unidad de Robos",
        "resumen_10_palabras": "Prueba de resolución final.",
        "estado_expediente": "En revisión",
    }

    guardar = client.post("/api/v1/guardar-denuncia", json=expediente_test)
    assert guardar.status_code == 201

    historial = client.get("/api/v1/denuncias")
    registros = historial.json()["denuncias"]
    indice = len(registros) - 1

    respuesta = client.patch(
        f"/api/v1/denuncias/{indice}/estado",
        json={
            "estado": "Canalizado",
            "resolucion_final": "Se derivó la denuncia a la unidad de robos y se cerró la intervención.",
            "observaciones_operador": "Se verificó la identidad del denunciante y el caso quedó resuelto."
        },
    )

    assert respuesta.status_code == 200
    payload = respuesta.json()
    assert payload["estado_expediente"] == "Canalizado"
    assert payload["resolucion_final"] == "Se derivó la denuncia a la unidad de robos y se cerró la intervención."
    assert payload["observaciones_operador"] == "Se verificó la identidad del denunciante y el caso quedó resuelto."