from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ProveedorLLM(str, Enum):
    """Proveedores de modelos soportados por Vig-IA."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"
    EXTERNO = "externo"


class DenunciaInput(BaseModel):
    """Esquema de entrada para la petición de triaje de denuncia."""
    codigo_agente: str = Field(
        ..., 
        description="Código de identificación del oficial de guardia",
        examples=["POL-98765"]
    )
    texto_denuncia: str = Field(
        ..., 
        min_length=15, 
        description="Narrativa desestructurada del hecho denunciado",
        examples=["Ayer a las 22:00 un sujeto me robó el teléfono a mano armada."]
    )
    proveedor: ProveedorLLM = Field(
        default=ProveedorLLM.OLLAMA,
        description="Proveedor del modelo (ollama, openai, groq, gemini o externo)"
    )
    modelo: Optional[str] = Field(
        default="qwen2.5-coder:7b",
        description="Nombre específico del modelo a ejecutar"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Clave de API opcional; cuando no se pasa, se usa la clave del entorno"
    )
    dual: bool = Field(
        default=False,
        description="Si se activa, ejecuta evaluación comparativa local y externa en paralelo"
    )

    @field_validator("codigo_agente")
    @classmethod
    def validar_codigo_agente(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("El código de agente es obligatorio.")
        return v


class MetricasPeticion(BaseModel):
    """Métricas de rendimiento, latencia y coste registradas por petición."""
    tokens_entrada: int = Field(default=0, description="Tokens del prompt de entrada")
    tokens_salida: int = Field(default=0, description="Tokens generados por el modelo")
    latencia_segundos: float = Field(..., description="Tiempo total de procesamiento en segundos")
    coste_estimado_usd: float = Field(default=0.0, description="Coste estimado de la consulta en USD")


class DenunciaOutput(BaseModel):
    """Esquema Type-Safe de salida estructurada devuelta tras el triaje."""
    codigo_agente: str = Field(..., description="Código del agente que gestionó la denuncia")
    razonamiento_cot: str = Field(..., description="Razonamiento intermedio Chain-of-Thought (CoT)")
    categoria: str = Field(..., description="Categoría principal del delito")
    nivel_urgencia: int = Field(..., ge=1, le=5, description="Nivel de prioridad (1 al 5)")
    resumen_10_palabras: str = Field(..., description="Resumen ejecutivo en máximo 10 palabras")
    departamento_asignado: str = Field(..., description="Unidad policial asignada")
    factores_riesgo: List[str] = Field(default_factory=list, description="Factores de riesgo detectados")
    metricas: MetricasPeticion = Field(..., description="Métricas de ejecución y coste")


class DenunciaComparativaOutput(BaseModel):
    """Resultado comparativo de la evaluación dual local vs externa."""
    resultado_local: Optional[DenunciaOutput] = Field(default=None, description="Dictamen generado por Ollama local")
    resultado_externo: Optional[DenunciaOutput] = Field(default=None, description="Dictamen generado por la API comercial")
    error_local: Optional[str] = Field(default=None, description="Error aislado del proveedor local")
    error_externo: Optional[str] = Field(default=None, description="Error aislado del proveedor externo")