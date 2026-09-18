import os
import json
import sys
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Permite importar el paquete app al ejecutar Streamlit desde frontend/.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.config import settings

# Configuración básica de la página
st.set_page_config(
    page_title="Vig-IA | Triaje Inteligente de Denuncias",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_BASE_URL = "http://127.0.0.1:8000"
OFICIALES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "oficiales.json")


def cargar_oficiales():
    if os.path.exists(OFICIALES_FILE):
        try:
            with open(OFICIALES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def autenticar_oficial(codigo: str, pin: str):
    oficiales = cargar_oficiales()
    codigo_clean = codigo.strip().upper()
    pin_clean = pin.strip()
    for oficial in oficiales:
        if oficial["codigo_agente"].strip().upper() == codigo_clean and oficial["pin"].strip() == pin_clean:
            return oficial
    return None


def comprobar_estado_servicios():
    estados = {"backend": False, "ollama": False, "gemini": bool(settings.GEMINI_API_KEY)}
    try:
        estados["backend"] = requests.get(f"{API_BASE_URL}/", timeout=3).status_code == 200
    except requests.RequestException:
        pass
    try:
        estados["ollama"] = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3).status_code == 200
    except requests.RequestException:
        pass
    return estados


def mostrar_estado_servicios():
    estados = comprobar_estado_servicios()
    st.sidebar.markdown("**Estado operativo**")
    etiquetas = {
        "backend": "FastAPI",
        "ollama": "Ollama",
        "gemini": "Gemini",
    }
    for clave, etiqueta in etiquetas.items():
        icono = "🟢" if estados[clave] else "🔴"
        detalle = "Disponible" if estados[clave] else "No disponible"
        if clave == "gemini" and estados[clave]:
            detalle = "Clave configurada"
        st.sidebar.caption(f"{icono} {etiqueta}: {detalle}")


st.markdown("""
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; }
    .sub-header { font-size: 1.1rem; color: #4B5563; }
    .login-box { background-color: #F3F4F6; padding: 25px; border-radius: 12px; border: 1px solid #D1D5DB; }
    .status-chip { display: inline-block; padding: 6px 12px; border-radius: 999px; font-weight: 600; font-size: 0.8rem; margin-right: 8px; }
    .chip-revision { background-color: #DBEAFE; color: #1D4ED8; }
    .chip-canalizado { background-color: #DCFCE7; color: #166534; }
    .panel-card { background: linear-gradient(135deg, #F8FAFC, #EEF2FF); border: 1px solid #E5E7EB; border-radius: 14px; padding: 16px; }
    .metric-mini { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px; }
    </style>
""", unsafe_allow_html=True)


if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["oficial_actual"] = None
if "historial_mensaje" not in st.session_state:
    st.session_state["historial_mensaje"] = ""
if "historial_mensaje_tipo" not in st.session_state:
    st.session_state["historial_mensaje_tipo"] = "info"


# --- PANTALLA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.markdown('<div class="main-header">🛡️ Vig-IA: Control de Acceso Policial</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Identifíquese con sus credenciales oficiales antes de acceder al motor de triaje.</div>', unsafe_allow_html=True)
    st.write("")

    col_l1, col_l2, col_l3 = st.columns(3)
    
    with col_l2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.subheader("🔒 Credenciales del Oficial")
        
        with st.form("form_login"):
            codigo_input = st.text_input("Código / Placa:", placeholder="Ej. POL-98765")
            pin_input = st.text_input("PIN de Acceso:", type="password", placeholder="****")
            btn_login = st.form_submit_button("🔑 Iniciar Sesión", use_container_width=True, type="primary")

            if btn_login:
                oficial_valido = autenticar_oficial(codigo_input, pin_input)
                if oficial_valido:
                    st.session_state["autenticado"] = True
                    st.session_state["oficial_actual"] = oficial_valido
                    st.rerun()
                else:
                    st.error("❌ Código de Agente o PIN incorrectos.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.stop()


# --- DASHBOARD PRINCIPAL ---
oficial = st.session_state["oficial_actual"]

# BARRA LATERAL
st.sidebar.image("https://img.icons8.com/color/96/shield.png", width=70)
st.sidebar.title("Vig-IA System")
st.sidebar.caption("Motor Type-Safe de Triaje Policial")

st.sidebar.markdown("---")
st.sidebar.subheader("👮 Oficial en Turno")
st.sidebar.success(f"**{oficial['nombre']} {oficial['apellido']}**\n\n📌 Placa: `{oficial['codigo_agente']}`")

if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
    st.session_state["autenticado"] = False
    st.session_state["oficial_actual"] = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("🛡️ Configuración activa: Ollama local con qwen2.5-coder:7b como modo principal.")
st.sidebar.caption("Modelo local: qwen2.5-coder:7b | AI externa: opcional (Gemini/AI Studio)")
mostrar_estado_servicios()
st.sidebar.markdown("---")
st.sidebar.info("🛡️ **Instrucción Ética**: La asignación de urgencia ignora variables demográficas para garantizar imparcialidad.")

proveedor_sel = "ollama"
modelo_sel = "qwen2.5-coder:7b"
api_key_input = settings.GEMINI_API_KEY


# PESTAÑAS PRINCIPALES
st.markdown('<div class="main-header">🛡️ Vig-IA: Centro de Triaje y Canalización</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">Oficial a cargo: <b>{oficial["nombre"]} {oficial["apellido"]}</b> ({oficial["codigo_agente"]})</div>', unsafe_allow_html=True)
st.write("")


def reset_turno():
    """Reinicia los resultados del turno activo para preparar el siguiente caso."""
    for key in ["resultado_comparativo", "ultimo_resultado", "texto_denuncia"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def render_tutorial_seccion(titulo, pasos):
    """Muestra un tutorial breve de uso para cada sección del dashboard."""
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader(f"🧭 {titulo}")
    for indice, paso in enumerate(pasos, start=1):
        st.markdown(f"**{indice}.** {paso}")
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")


def render_resumen_comparativo(local, externo):
    """Muestra las coincidencias y divergencias principales entre ambos dictámenes."""
    if not local or not externo:
        return

    campos = [
        ("Categoría", "categoria"),
        ("Nivel de urgencia", "nivel_urgencia"),
        ("Departamento", "departamento_asignado"),
    ]
    st.markdown("#### Comparativa rápida")
    columnas = st.columns([1.4, 2, 2, 1.5])
    columnas[0].markdown("**Criterio**")
    columnas[1].markdown("**Ollama**")
    columnas[2].markdown("**Gemini**")
    columnas[3].markdown("**Estado**")
    discrepancias = []

    for etiqueta, clave in campos:
        valor_local = local.get(clave, "-")
        valor_externo = externo.get(clave, "-")
        coincide = valor_local == valor_externo
        if not coincide:
            discrepancias.append(etiqueta)
        columnas = st.columns([1.4, 2, 2, 1.5])
        columnas[0].write(etiqueta)
        columnas[1].write(str(valor_local))
        columnas[2].write(str(valor_externo))
        if coincide:
            columnas[3].success("Coincide")
        else:
            columnas[3].warning("Revisar")

    if discrepancias:
        st.warning("Hay diferencias en: " + ", ".join(discrepancias) + ". Se recomienda revisión humana.")
    else:
        st.success("Ambos modelos coinciden en categoría, urgencia y departamento.")


def guardar_expediente(result, texto_actual, estado_expediente, reiniciar=False):
    expediente = {
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nombre_oficial": f"{oficial['nombre']} {oficial['apellido']}",
        "texto_original": texto_actual,
        "estado_expediente": estado_expediente,
        **result,
    }
    save_resp = requests.post(f"{API_BASE_URL}/api/v1/guardar-denuncia", json=expediente, timeout=10)
    if save_resp.status_code == 201:
        st.success(f"Expediente guardado como: {estado_expediente}.")
        if reiniciar:
            st.balloons()
            reset_turno()
    else:
        st.error(f"No se pudo guardar el expediente: {save_resp.text}")


def render_dictamen_panel(panel, result, titulo, boton_key, texto_actual):
    """Renderiza cada dictamen de la comparación dual con su acción de validación."""
    with panel:
        if result is None:
            st.error(f"❌ {titulo} no disponible")
            return

        urgencia = result.get("nivel_urgencia", 0)
        colores = {1: "#10B981", 2: "#3B82F6", 3: "#F59E0B", 4: "#EF4444", 5: "#7F1D1D"}
        color_bg = colores.get(urgencia, "#6B7280")
        st.markdown(
            f"""
            <div style="background-color:{color_bg}; color:white; padding:12px; border-radius:8px; text-align:center; font-weight:bold; font-size:1.1rem;">
                {titulo}: {urgencia} / 5
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")

        c1, c2 = st.columns(2)
        c1.metric("Categoría", result.get("categoria", "-"))
        c2.metric("Unidad", result.get("departamento_asignado", "-"))

        st.markdown(f"**Resumen Ejecutivo:** _{result.get('resumen_10_palabras', '-')}_")

        if result.get("factores_riesgo"):
            st.markdown("**Factores de Riesgo:**")
            st.write(", ".join([f"⚠️ `{f}`" for f in result["factores_riesgo"]]))

        with st.expander("🧠 Ver análisis del dictamen", expanded=False):
            st.info(result.get("razonamiento_cot", "-"))

        m = result.get("metricas", {})
        st.caption(
            f"⏱️ **Latencia:** {m.get('latencia_segundos', 0)}s | "
            f"🔢 **Tokens:** {m.get('tokens_entrada', 0)} in / {m.get('tokens_salida', 0)} out | "
            f"💰 **Coste Est.:** ${m.get('coste_estimado_usd', 0)} USD"
        )

        st.markdown("---")
        acciones = st.columns(2)
        if acciones[0].button("Guardar en revisión", key=f"{boton_key}_revision", use_container_width=True):
            guardar_expediente(result, texto_actual, "En revisión")
        if acciones[1].button("Canalizar expediente", key=f"{boton_key}_canalizar", use_container_width=True):
            guardar_expediente(result, texto_actual, "Canalizado", reiniciar=True)


def exportar_historial_csv(df):
    """Prepara un CSV del histórico para exportación."""
    csv_data = df.to_csv(index=False, encoding="utf-8")
    st.download_button(
        label="📥 Exportar histórico CSV",
        data=csv_data,
        file_name="historial_vig_ia.csv",
        mime="text/csv",
        use_container_width=True,
    )


def resumen_turno(df):
    """Calcula y muestra métricas operativas del turno."""
    if df.empty:
        return

    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader("📊 Resumen del turno")
    metricas = st.columns(4)
    metricas[0].metric("Total casos", len(df))
    metricas[1].metric("Urgencia alta", int((df["nivel_urgencia"] >= 4).sum()))
    metricas[2].metric("Canalizados", int((df["estado_expediente"] == "Canalizado").sum()))
    metricas[3].metric("En revisión", int((df["estado_expediente"] == "En revisión").sum()))
    st.markdown('</div>', unsafe_allow_html=True)


tab1, tab2 = st.tabs(["📝 Recepción de Denuncia", "📂 Histórico de Expedientes"])

with tab1:
    render_tutorial_seccion(
        "Guía rápida: recepción de denuncia",
        [
            "Escribe la denuncia del ciudadano en lenguaje natural, sin necesidad de estructurarla demasiado.",
            "Pulsa \"Procesar y Triar Denuncia\" para comparar el resultado del modelo local y el externo.",
            "Revisa la categoría, la urgencia y el departamento sugeridos antes de tomar una decisión final.",
            "Si los dos modelos discrepan, el sistema te avisará para que revises el caso con más cuidado.",
        ],
    )
    st.subheader("1. Ingesta de Narrativa")
    with st.form("form_triaje_dual", clear_on_submit=False):
        texto_denuncia = st.text_area(
            "Declaración del ciudadano (Texto libre desestructurado):",
            height=220,
            placeholder="Ejemplo: Ayer por la noche, un sujeto me arrebató el bolso a la fuerza en la calle Mayor...",
            key="texto_denuncia",
        )
        btn_procesar = st.form_submit_button("🚀 Procesar y Triar Denuncia", use_container_width=True, type="primary")

    if btn_procesar:
        if not texto_denuncia.strip() or len(texto_denuncia) < 15:
            st.warning("⚠️ La narrativa debe tener al menos 15 caracteres.")
        else:
            payload = {
                "codigo_agente": oficial["codigo_agente"],
                "texto_denuncia": texto_denuncia,
                "proveedor": proveedor_sel,
                "modelo": modelo_sel,
                "api_key": api_key_input,
                "dual": True,
            }

            with st.spinner("Procesando triaje dual en paralelo con Ollama y proveedor comercial..."):
                try:
                    resp = requests.post(f"{API_BASE_URL}/api/v1/triaje", json=payload, timeout=180)
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state["resultado_comparativo"] = data
                        st.session_state["ultimo_resultado"] = data
                        st.success("✅ Triaje dual completado y comparado en paralelo.")
                    else:
                        st.error(f"❌ Error en la API ({resp.status_code}): {resp.text}")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 No se pudo conectar con el backend de FastAPI.")

    st.divider()
    render_tutorial_seccion(
        "Guía rápida: dictamen dual",
        [
            "Aquí se comparan dos resultados: uno del modelo local y otro del externo.",
            "Mira la comparación rápida para ver si coinciden en categoría, urgencia y unidad asignada.",
            "Si hay discrepancias, el sistema te indica que debe revisarse el caso con criterio humano.",
            "Puedes guardar el expediente en revisión o canalizarlo directamente cuando decidas.",
        ],
    )
    st.subheader("2. Dictamen Type-Safe Dual")

    if "resultado_comparativo" in st.session_state:
        comparativo = st.session_state["resultado_comparativo"]
        local = comparativo.get("resultado_local")
        externo = comparativo.get("resultado_externo")
        error_local = comparativo.get("error_local")
        error_externo = comparativo.get("error_externo")

        if local is None and error_local:
            st.warning(f"⚠️ Ollama local no pudo responder: {error_local}")
        if externo is None and error_externo:
            st.warning(f"⚠️ API externa no pudo responder: {error_externo}")

        _comparativa_renderizada = render_resumen_comparativo(local, externo)
        st.divider()
        col_local, col_externo = st.columns(2, gap="large")
        _ = render_dictamen_panel(
            col_local,
            local,
            "Ollama Local",
            "btn_validar_ollama",
            texto_denuncia,
        )
        _ = render_dictamen_panel(
            col_externo,
            externo,
            "API Comercial",
            "btn_validar_externo",
            texto_denuncia,
        )
    else:
        st.info("El dictamen dual aparecerá aquí después de procesar una denuncia.")
with tab2:
    render_tutorial_seccion(
        "Guía rápida: historial y canalización",
        [
            "Usa la búsqueda para encontrar un caso por código, categoría, resumen o fecha.",
            "Filtra por urgencia, categoría o estado para centrarte en los expedientes que te interesan.",
            "Selecciona un caso para ver su resumen y su explicación de resolución antes de cambiarlo.",
            "Cuando decidas, cambia el estado a revisión o canalizado y deja una nota de cierre si hace falta.",
        ],
    )
    mensaje_historial = st.session_state.pop("historial_mensaje", "")
    tipo_historial = st.session_state.pop("historial_mensaje_tipo", "info")
    if mensaje_historial:
        if tipo_historial == "success":
            st.success(mensaje_historial)
        elif tipo_historial == "warning":
            st.warning(mensaje_historial)
        else:
            st.info(mensaje_historial)

    st.subheader("📂 Denuncias Canalizadas")
    top_bar = st.columns([1, 1])
    with top_bar[0]:
        if st.button("🔄 Actualizar Historial", use_container_width=True):
            st.rerun()
    with top_bar[1]:
        st.caption("Gestión rápida del flujo operativo del turno.")

    try:
        hist_resp = requests.get(f"{API_BASE_URL}/api/v1/denuncias", timeout=10)
        if hist_resp.status_code == 200:
            denuncias = hist_resp.json()["denuncias"]
            if denuncias:
                df = pd.DataFrame(denuncias)

                if "estado_expediente" not in df.columns:
                    df["estado_expediente"] = "En revisión"
                else:
                    df["estado_expediente"] = df["estado_expediente"].fillna("En revisión")

                if "codigo_agente" not in df.columns:
                    df["codigo_agente"] = "-"
                if "categoria" not in df.columns:
                    df["categoria"] = "Sin categoría"
                if "nivel_urgencia" not in df.columns:
                    df["nivel_urgencia"] = 0
                if "departamento_asignado" not in df.columns:
                    df["departamento_asignado"] = "No definido"
                if "resumen_10_palabras" not in df.columns:
                    df["resumen_10_palabras"] = "Sin resumen"

                filtro_texto = st.text_input(
                    "🔎 Búsqueda rápida (código, categoría, resumen o fecha)",
                    placeholder="Ej. POL-98765, Robo, 2026-09-18",
                )
                filtros = st.columns(3)
                niveles = sorted(df["nivel_urgencia"].dropna().astype(int).unique().tolist()) if "nivel_urgencia" in df else []
                nivel_seleccionado = filtros[0].multiselect("Nivel de urgencia", niveles)
                categorias = sorted(df["categoria"].dropna().astype(str).unique().tolist()) if "categoria" in df else []
                categoria_seleccionada = filtros[1].multiselect("Categoría", categorias)
                estados = sorted(df["estado_expediente"].dropna().astype(str).unique().tolist())
                estado_seleccionado = filtros[2].selectbox("Estado del expediente", ["Todos"] + estados)

                if filtro_texto:
                    df = df[df.astype(str).apply(lambda columna: columna.str.contains(filtro_texto, case=False, na=False)).any(axis=1)]
                if nivel_seleccionado:
                    df = df[df["nivel_urgencia"].isin(nivel_seleccionado)]
                if categoria_seleccionada:
                    df = df[df["categoria"].isin(categoria_seleccionada)]
                if estado_seleccionado != "Todos":
                    df = df[df["estado_expediente"] == estado_seleccionado]

                urgentes = int((df["nivel_urgencia"] >= 4).sum()) if "nivel_urgencia" in df else 0
                pendientes = int((df["estado_expediente"] == "En revisión").sum()) if "estado_expediente" in df else 0
                metricas = st.columns(3)
                metricas[0].metric("Denuncias visibles", len(df))
                metricas[1].metric("Urgencia alta", urgentes)
                metricas[2].metric("Pendientes revisión", pendientes)

                resumen_turno(df)
                exportar_historial_csv(df)

                cols = [
                    "fecha_registro",
                    "codigo_agente",
                    "nombre_oficial",
                    "estado_expediente",
                    "categoria",
                    "nivel_urgencia",
                    "departamento_asignado",
                    "resumen_10_palabras",
                ]

                if df.empty:
                    st.info("No hay denuncias que coincidan con los filtros seleccionados.")
                else:
                    codigo_busqueda = st.text_input(
                        "Código rápido para abrir expediente",
                        placeholder="Ej. POL-98765 o parte del código",
                        key="codigo_busqueda_historial",
                    )
                    indice_default = 0
                    if codigo_busqueda:
                        candidatos = df[df["codigo_agente"].astype(str).str.contains(codigo_busqueda, case=False, na=False)]
                        if not candidatos.empty:
                            indice_default = candidatos.index[0]
                            st.success(f"Se localizó un expediente compatible para: {codigo_busqueda}")

                    indices_visibles = df.index.tolist()
                    indice_seleccionado = st.selectbox(
                        "Caso a actualizar",
                        indices_visibles,
                        index=indices_visibles.index(indice_default) if indice_default in indices_visibles else 0,
                        format_func=lambda indice: (
                            f"{df.loc[indice].get('codigo_agente', '-')} | "
                            f"{df.loc[indice].get('categoria', 'Sin categoría')} | "
                            f"{df.loc[indice].get('estado_expediente', 'En revisión')}"
                        ),
                    )

                    expediente = df.loc[indice_seleccionado].to_dict()
                    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                    st.subheader("🧾 Resumen del expediente seleccionado")
                    estado_color = "chip-revision" if expediente.get("estado_expediente") == "En revisión" else "chip-canalizado"
                    estado_texto = expediente.get("estado_expediente", "En revisión")
                    st.markdown(f'<span class="status-chip {estado_color}">{estado_texto}</span>', unsafe_allow_html=True)
                    st.write(f"**Código:** {expediente.get('codigo_agente', '-')} | **Oficial:** {expediente.get('nombre_oficial', '-')} | **Fecha:** {expediente.get('fecha_registro', '-')}")
                    st.write(f"**Categoría:** {expediente.get('categoria', '-')} | **Urgencia:** {expediente.get('nivel_urgencia', '-')} | **Departamento:** {expediente.get('departamento_asignado', '-')}")
                    st.write(f"**Resumen:** {expediente.get('resumen_10_palabras', '-')}")

                    razonamiento = expediente.get("razonamiento_cot") or expediente.get("razonamiento") or "Sin explicación de la resolución disponible."
                    st.markdown("**Cómo se resolvió el caso:**")
                    st.info(razonamiento[:700] + ("..." if len(razonamiento) > 700 else ""))
                    st.markdown('</div>', unsafe_allow_html=True)

                    nueva_fila = st.columns([1, 1])
                    with nueva_fila[0]:
                        nuevo_estado = st.selectbox("Nuevo estado", ["En revisión", "Canalizado"], index=0 if expediente.get("estado_expediente") == "En revisión" else 1)
                    with nueva_fila[1]:
                        resolucion_final = st.text_area(
                            "Resolución final / cómo se cerró el caso",
                            value=str(expediente.get("resolucion_final", "")),
                            height=120,
                            key="resolucion_final_input",
                        )

                    observaciones_operador = st.text_area(
                        "Observaciones del oficial",
                        value=str(expediente.get("observaciones_operador", "")),
                        height=100,
                    )

                    if st.button("Actualizar estado del caso", type="primary", use_container_width=True):
                        estado_resp = requests.patch(
                            f"{API_BASE_URL}/api/v1/denuncias/{indice_seleccionado}/estado",
                            json={
                                "estado": nuevo_estado,
                                "resolucion_final": resolucion_final,
                                "observaciones_operador": observaciones_operador,
                            },
                            timeout=10,
                        )
                        if estado_resp.status_code == 200:
                            st.session_state["historial_mensaje"] = f"Estado actualizado correctamente: {nuevo_estado}."
                            st.session_state["historial_mensaje_tipo"] = "success"
                            st.rerun()
                        else:
                            st.session_state["historial_mensaje"] = f"No se pudo actualizar el estado: {estado_resp.text}"
                            st.session_state["historial_mensaje_tipo"] = "warning"
                            st.rerun()

                    st.dataframe(
                        df[[c for c in cols if c in df.columns]],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.info("Todavía no hay denuncias canalizadas en el histórico.")
    except Exception as e:
        st.warning("No se pudo cargar el historial.")