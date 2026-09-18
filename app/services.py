import json
import logging
import random
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

import requests
from pydantic import ValidationError

from app.config import settings
from app.prompts import obtener_prompt_sistema, construir_prompt_usuario
from app.schemas import (
    DenunciaComparativaOutput,
    DenunciaInput,
    DenunciaOutput,
    MetricasPeticion,
    ProveedorLLM,
)


def _limpiar_json_markdown(texto: str) -> str:
    """Extrae y limpia el bloque JSON del texto generado por el LLM."""
    patron = r"```(?:json)?\s*([\s\S]*?)\s*```"
    coincidencia = re.search(patron, texto)
    if coincidencia:
        return coincidencia.group(1).strip()
    return texto.strip()


def _validar_resultado_llm(
    codigo_agente: str,
    texto_raw: str,
    tokens_in: int,
    tokens_out: int,
    latencia: float,
    coste_estimado: float,
) -> DenunciaOutput:
    """Valida y normaliza la respuesta del modelo siguiendo estrictamente el esquema Pydantic."""
    texto_json = _limpiar_json_markdown(texto_raw)
    datos_json = json.loads(texto_json)
    datos_json["codigo_agente"] = codigo_agente
    datos_json["metricas"] = MetricasPeticion(
        tokens_entrada=tokens_in,
        tokens_salida=tokens_out,
        latencia_segundos=latencia,
        coste_estimado_usd=round(coste_estimado, 6),
    ).model_dump()
    return DenunciaOutput(**datos_json)


def _ejecutar_ollama(prompt_sistema: str, prompt_usuario: str, modelo: str) -> Tuple[str, int, int]:
    """Invocación local a Ollama con fallback a modelos instalados."""
    modelos = [modelo or settings.OLLAMA_DEFAULT_MODEL, "qwen2.5-coder:7b", "qwen3-coder:30b", "llama3.2:3b", "ultron:latest"]
    ultimo_error = None

    for nombre_modelo in modelos:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": nombre_modelo,
            "system": prompt_sistema,
            "prompt": prompt_usuario,
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        try:
            respuesta = requests.post(url, json=payload, timeout=180)
            if respuesta.status_code == 404:
                ultimo_error = RuntimeError(f"Modelo Ollama no encontrado: {nombre_modelo}")
                continue
            respuesta.raise_for_status()
            data = respuesta.json()
            return data.get("response", ""), data.get("prompt_eval_count", 0), data.get("eval_count", 0)
        except requests.RequestException as e:
            ultimo_error = e
            continue

    raise RuntimeError(f"Ollama no respondió correctamente: {ultimo_error}")


def _ejecutar_api_externa(
    prompt_sistema: str,
    prompt_usuario: str,
    proveedor: ProveedorLLM,
    modelo: str,
    api_key_override: str = None,
    max_retries: int = 3,
) -> Tuple[str, int, int]:
    """Invocación a APIs comerciales externas (OpenAI, Groq, Gemini o genérica OpenAI)."""
    logger = logging.getLogger(__name__)

    if proveedor == ProveedorLLM.OPENAI:
        base_url = "https://api.openai.com/v1/chat/completions"
        api_key = api_key_override or os.getenv("OPENAI_API_KEY", "") or settings.EXTERNO_API_KEY
        candidatos_modelos = [modelo or "gpt-4o-mini", "gpt-4.1-mini", "gpt-3.5-turbo"]
    elif proveedor == ProveedorLLM.GROQ:
        base_url = "https://api.groq.com/openai/v1/chat/completions"
        api_key = api_key_override or settings.GROQ_API_KEY
        candidatos_modelos = [modelo or "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
    elif proveedor == ProveedorLLM.GEMINI:
        api_key = api_key_override or settings.GEMINI_API_KEY
        modelo_gemini = modelo if modelo and modelo.startswith("gemini-") else settings.EXTERNO_DEFAULT_MODEL
        candidatos_modelos = list(dict.fromkeys([
            modelo_gemini,
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
        ]))
        base_url = f"{settings.EXTERNO_BASE_URL}/models/{{modelo}}:generateContent?key={api_key}"
    else:
        base_url = f"{settings.EXTERNO_BASE_URL}/chat/completions"
        api_key = api_key_override or settings.EXTERNO_API_KEY
        candidatos_modelos = [modelo or settings.EXTERNO_DEFAULT_MODEL]

    if not api_key:
        raise ValueError(
            f"No se proporcionó una API Key para el proveedor {proveedor.value.upper()}. "
            "La clave se toma desde el archivo .env del proyecto."
        )

    headers = {"Content-Type": "application/json"}
    if proveedor in {ProveedorLLM.OPENAI, ProveedorLLM.GROQ}:
        headers["Authorization"] = f"Bearer {api_key}"

    ultimo_error = None
    for intento in range(max_retries):
        for modelo_actual in candidatos_modelos:
            try:
                if proveedor == ProveedorLLM.GEMINI:
                    endpoint = base_url.format(modelo=modelo_actual)
                    payload = {
                        "contents": [{"parts": [{"text": f"{prompt_sistema}\n\n{prompt_usuario}"}]}],
                        "generationConfig": {
                            "temperature": 0.1,
                            "responseMimeType": "application/json",
                        },
                    }
                    respuesta = requests.post(endpoint, headers=headers, json=payload, timeout=60)
                else:
                    payload = {
                        "model": modelo_actual,
                        "messages": [
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        "temperature": 0.1,
                    }
                    if proveedor in {ProveedorLLM.OPENAI, ProveedorLLM.GROQ}:
                        payload["response_format"] = {"type": "json_object"}
                    respuesta = requests.post(base_url, headers=headers, json=payload, timeout=60)

                if respuesta.status_code in {429, 500, 503}:
                    detalle = respuesta.text
                    try:
                        detalle = respuesta.json().get("error", {}).get("message", detalle)
                    except Exception:
                        pass
                    backoff = min(8, (2 ** intento) + random.uniform(0.5, 1.5))
                    logger.warning(
                        "Gemini temporal unavailable (%s) for model %s. Retry in %.2fs. Details: %s",
                        respuesta.status_code,
                        modelo_actual,
                        backoff,
                        detalle,
                    )
                    time.sleep(backoff)
                    continue

                if respuesta.status_code == 404:
                    detalle = respuesta.text
                    try:
                        detalle = respuesta.json().get("error", {}).get("message", detalle)
                    except Exception:
                        pass
                    logger.warning("Modelo no disponible en %s: %s", proveedor.value.upper(), detalle)
                    ultimo_error = RuntimeError(f"Modelo no disponible en {proveedor.value.upper()}: {detalle}")
                    continue
                if respuesta.status_code == 400:
                    detalle = respuesta.text
                    try:
                        detalle = respuesta.json().get("error", {}).get("message", detalle)
                    except Exception:
                        pass
                    ultimo_error = RuntimeError(f"Petición inválida en {proveedor.value.upper()}: {detalle}")
                    continue
                respuesta.raise_for_status()
                data = respuesta.json()
                if proveedor == ProveedorLLM.GEMINI:
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError(f"La respuesta de {proveedor.value.upper()} no devolvió contenido.")
                    text_parts = candidates[0].get("content", {}).get("parts", [])
                    if not text_parts:
                        raise ValueError(f"La respuesta de {proveedor.value.upper()} no devolvió contenido.")
                    texto_salida = "".join(part.get("text", "") for part in text_parts)
                    usage = data.get("usageMetadata", {})
                    tokens_in = usage.get("promptTokenCount", 0)
                    tokens_out = usage.get("candidatesTokenCount", 0)
                    return texto_salida, tokens_in, tokens_out

                choices = data.get("choices", [])
                if not choices:
                    raise ValueError(f"La respuesta de {proveedor.value.upper()} no devolvió mensajes.")
                texto_salida = choices[0]["message"]["content"]
                usage = data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
                return texto_salida, tokens_in, tokens_out
            except (requests.RequestException, KeyError, TypeError, ValueError, IndexError) as e:
                ultimo_error = e
                backoff = min(8, (2 ** intento) + random.uniform(0.5, 1.5))
                logger.warning("Error en %s con modelo %s: %s. Retry in %.2fs.", proveedor.value.upper(), modelo_actual, e, backoff)
                time.sleep(backoff)

    mensaje = str(ultimo_error) if ultimo_error else "Error desconocido"
    raise RuntimeError(f"Error tras {max_retries} reintentos en {proveedor.value.upper()}: {mensaje}")


def _procesar_triaje_individual(datos_entrada: DenunciaInput) -> DenunciaOutput:
    """Procesa un único triaje con un proveedor concreto."""
    inicio = time.perf_counter()
    prompt_sistema = obtener_prompt_sistema()
    prompt_usuario = construir_prompt_usuario(
        codigo_agente=datos_entrada.codigo_agente,
        texto_denuncia=datos_entrada.texto_denuncia,
    )

    if datos_entrada.proveedor == ProveedorLLM.OLLAMA:
        texto_raw, tokens_in, tokens_out = _ejecutar_ollama(
            prompt_sistema,
            prompt_usuario,
            datos_entrada.modelo or settings.OLLAMA_DEFAULT_MODEL,
        )
        coste_estimado = 0.0
    else:
        texto_raw, tokens_in, tokens_out = _ejecutar_api_externa(
            prompt_sistema,
            prompt_usuario,
            datos_entrada.proveedor,
            datos_entrada.modelo or settings.EXTERNO_DEFAULT_MODEL,
            api_key_override=datos_entrada.api_key,
        )
        coste_estimado = ((tokens_in / 1000) * settings.COSTO_INPUT_1K_TOKENS) + (
            (tokens_out / 1000) * settings.COSTO_OUTPUT_1K_TOKENS
        )

    fin = time.perf_counter()
    latencia = round(fin - inicio, 3)

    try:
        return _validar_resultado_llm(
            codigo_agente=datos_entrada.codigo_agente,
            texto_raw=texto_raw,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latencia=latencia,
            coste_estimado=coste_estimado,
        )
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as e:
        raise ValueError(f"Fallo de Type-Safety: Respuesta corrupta o fuera de esquema. Detalles: {str(e)}")


def procesar_triaje_denuncia(datos_entrada: DenunciaInput) -> DenunciaOutput:
    """Servicio principal de triaje con soporte para múltiples proveedores."""
    if datos_entrada.dual:
        return procesar_triaje_dual(datos_entrada)
    return _procesar_triaje_individual(datos_entrada)


def procesar_triaje_dual(datos_entrada: DenunciaInput) -> DenunciaComparativaOutput:
    """Ejecuta local y externo en paralelo para comparar dictámenes simultáneamente."""
    local_input = DenunciaInput(
        codigo_agente=datos_entrada.codigo_agente,
        texto_denuncia=datos_entrada.texto_denuncia,
        proveedor=ProveedorLLM.OLLAMA,
        modelo=datos_entrada.modelo or settings.OLLAMA_DEFAULT_MODEL,
        api_key=None,
        dual=False,
    )

    proveedor_externo = (
        datos_entrada.proveedor
        if datos_entrada.proveedor in {ProveedorLLM.OPENAI, ProveedorLLM.GROQ, ProveedorLLM.GEMINI, ProveedorLLM.EXTERNO}
        else ProveedorLLM.GEMINI
    )
    externo_input = DenunciaInput(
        codigo_agente=datos_entrada.codigo_agente,
        texto_denuncia=datos_entrada.texto_denuncia,
        proveedor=proveedor_externo,
        modelo=(
            datos_entrada.modelo
            if datos_entrada.modelo and datos_entrada.modelo.startswith(("gpt-", "llama-", "gemma", "gemini-"))
            else settings.EXTERNO_DEFAULT_MODEL
        ),
        api_key=datos_entrada.api_key,
        dual=False,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_local = executor.submit(_procesar_triaje_individual, local_input)
        futuro_externo = executor.submit(_procesar_triaje_individual, externo_input)

        resultado_local = None
        resultado_externo = None
        error_local = None
        error_externo = None

        for nombre, futuro in {"local": futuro_local, "externo": futuro_externo}.items():
            try:
                if nombre == "local":
                    resultado_local = futuro.result()
                else:
                    resultado_externo = futuro.result()
            except Exception as exc:  # pragma: no cover - errores aislados de cada proveedor
                if nombre == "local":
                    error_local = str(exc)
                else:
                    error_externo = str(exc)

    return DenunciaComparativaOutput(
        resultado_local=resultado_local,
        resultado_externo=resultado_externo,
        error_local=error_local,
        error_externo=error_externo,
    )