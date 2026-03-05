import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# ==========================
# CONFIG GENERAL
# ==========================
API_URL = "https://proyecto-salud-digital.onrender.com"

st.set_page_config(page_title="Dashboard Clínica", layout="wide")
st.title("Dashboard de Gestión Clínica")

# ==========================
# LOGIN
# ==========================
with st.sidebar.form("login_form"):
    st.header("Login")
    access_key = st.text_input("Access Key", type="password")
    permission_key = st.text_input("Permission Key", type="password")
    submitted = st.form_submit_button("Ingresar")

if not submitted:
    st.stop()

HEADERS = {
    "x-access-key": access_key,
    "x-permission-key": permission_key
}

# ==========================
# FUNCIONES API (CACHE SEGURO)
# ==========================
@st.cache_data(ttl=15)
def fetch_patients(access_key, permission_key):
    headers = {
        "x-access-key": access_key,
        "x-permission-key": permission_key
    }
    resp = requests.get(f"{API_URL}/fhir/Patient?limit=100&offset=0", headers=headers)
    if resp.status_code != 200:
        return None
    return pd.DataFrame(resp.json()["data"])


@st.cache_data(ttl=15)
def fetch_observations(access_key, permission_key):
    headers = {
        "x-access-key": access_key,
        "x-permission-key": permission_key
    }

    resp = requests.get(
        f"{API_URL}/fhir/Observation?limit=500&offset=0",
        headers=headers
    )

    if resp.status_code != 200:
        return None, None

    json_data = resp.json()

    obs_df = pd.DataFrame(json_data.get("data", []))
    alerts_df = pd.DataFrame(json_data.get("alerts", []))

    return obs_df, alerts_df

# ==========================
# CARGA DATOS
# ==========================
patients_df = fetch_patients(access_key, permission_key)
obs_df, alerts_df = fetch_observations(access_key, permission_key)

if patients_df is None or patients_df.empty:
    st.error("No se pudieron cargar pacientes o no tienes permisos.")
    st.stop()

if obs_df is None:
    st.error("No se pudieron cargar observaciones.")
    st.stop()

# ==========================
# DETECTAR ROL
# ==========================
is_admin = "serialized_data" in patients_df.columns
is_patient = not is_admin and len(patients_df) == 1
is_medico = not is_admin and not is_patient

# ==========================
# SELECCIÓN DE PACIENTE
# ==========================
# ADMIN
if is_admin:
    st.subheader("Lista de Pacientes (Admin)")
    st.dataframe(patients_df[["id"]], use_container_width=True)
    st.stop()

# PACIENTE
if is_patient:
    selected_patient = patients_df.iloc[0]["id"]
    st.subheader(f"Paciente: {selected_patient}")

# MÉDICO
if is_medico:

    st.subheader("Pacientes Registrados")

    display_cols = [col for col in 
        ["id","given_name","family_name","gender","birth_date"]
        if col in patients_df.columns
    ]

    display_df = patients_df[display_cols].reset_index(drop=True)

    selected_index = st.number_input(
        "Seleccione el número de paciente",
        min_value=0,
        max_value=len(display_df)-1,
        step=1
    )

    st.dataframe(display_df, use_container_width=True)

    selected_patient = display_df.iloc[selected_index]["id"]

# ==========================
# INFO DEL PACIENTE
# ==========================
patient_info = patients_df[patients_df["id"] == selected_patient]

if not patient_info.empty:
    info = patient_info.iloc[0]
    st.markdown("### Información del Paciente")
    col1, col2, col3 = st.columns(3)
    col1.metric("Nombre", f"{info.get('given_name', '')} {info.get('family_name', '')}")
    col2.metric("Género", info.get("gender", "N/A"))
    col3.metric("Fecha Nacimiento", info.get("birth_date", "N/A"))

# ==========================
# ALERTAS CLÍNICAS (SOLO MÉDICO)
# ==========================
if is_medico and alerts_df is not None and not alerts_df.empty:

    patient_alerts = alerts_df[
        alerts_df["patient_id"] == selected_patient
    ]

    if not patient_alerts.empty:
        st.error("⚠️ ALERTAS CLÍNICAS ACTIVAS")

        for _, alert in patient_alerts.iterrows():
            st.warning(
                f"{alert['code']} = {alert['value']} → {alert['message']}"
            )

# ==========================
# NUEVA OBSERVACIÓN
# ==========================
if is_medico:
    st.subheader("Registrar Nueva Observación")

    with st.form("new_obs_form"):
        col1, col2 = st.columns(2)

        code = col1.selectbox(
            "Tipo de Signo Vital",
            [
                "heart_rate",
                "temperature",
                "glucose",
                "platelets",
                "systolic_pressure",
                "diastolic_pressure"
            ]
        )

        value = col2.number_input("Valor", step=0.1)

        unit = st.text_input("Unidad")

        submit_obs = st.form_submit_button("Guardar Observación")

        # VALIDACIÓN DE IMPOSIBLES (SOLO VISUAL)
        impossible = False

        if code == "temperature" and value > 45:
            impossible = True
        if code == "heart_rate" and value > 250:
            impossible = True
        if code == "systolic_pressure" and value > 350:
            impossible = True

        if impossible:
            st.error("⚠ Valor clínicamente imposible detectado")

        if submit_obs:
            payload = {
                "patient_id": selected_patient,
                "code": code,
                "value": value,
                "unit": unit
            }

            r = requests.post(
                f"{API_URL}/fhir/Observation",
                headers=HEADERS,
                json=payload
            )

            if r.status_code == 200:
                st.success("Observación registrada")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Error al guardar observación")

# ==========================
# FILTRAR OBSERVACIONES
# ==========================
# ADMIN no recibe observaciones reales
if "total" in obs_df.columns:
    st.subheader("Resumen de Observaciones por Paciente")
    st.dataframe(obs_df, use_container_width=True)
    st.stop()

# Si no hay columna patient_id no seguimos
if obs_df.empty or "patient_id" not in obs_df.columns:
    st.info("No hay observaciones disponibles.")
    st.stop()

patient_obs = obs_df[obs_df["patient_id"] == selected_patient].copy()

if patient_obs.empty:
    st.info("No hay observaciones registradas para este paciente.")
    st.stop()

# ==========================
# LIMPIEZA DATOS
# ==========================
if not patient_obs.empty:

    patient_obs["value_num"] = pd.to_numeric(
        patient_obs.get("value"),
        errors="coerce"
    )

    if "created_at" in patient_obs.columns:
        patient_obs["created_at"] = pd.to_datetime(
            patient_obs["created_at"]
        )

# ==========================
# REGLAS DE OUTLIERS
# ==========================
def is_outlier(value, code):
    if value is None:
        return False

    if code == "temperature":
        return value < 30 or value > 45
    if code == "heart_rate":
        return value < 30 or value > 250
    if code == "systolic_pressure":
        return value < 50 or value > 300

    return False

if not patient_obs.empty:
    patient_obs["outlier"] = patient_obs.apply(
        lambda row: is_outlier(row.get("value_num"), row.get("code")),
        axis=1
    )

# ==========================
# GRAFICAS
# ==========================
if not patient_obs.empty:

    st.subheader("Tendencias de Signos Vitales")

    patient_obs["value_num"] = pd.to_numeric(
        patient_obs["value"], errors="coerce"
    )
    patient_obs["created_at"] = pd.to_datetime(
        patient_obs["created_at"]
    )

    for code in patient_obs["code"].unique():

        df_code = patient_obs[
            (patient_obs["code"] == code) &
            (patient_obs["value_num"].notna())
        ].sort_values("created_at")

        if df_code.empty:
            continue

        fig = px.line(
            df_code,
            x="created_at",
            y="value_num",
            title=f"{code} en el tiempo",
            markers=True
        )

        # Valores anormales (backend ya los detectó)
        if is_medico and "is_abnormal" in df_code.columns:

            abnormal_points = df_code[df_code["is_abnormal"] == True]

            if not abnormal_points.empty:
                fig.add_scatter(
                    x=abnormal_points["created_at"],
                    y=abnormal_points["value_num"],
                    mode="markers",
                    marker=dict(color="red", size=14),
                    name="Valor Anormal"
                )

        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No hay observaciones para este paciente.")

if is_medico and not patient_obs.empty:

    st.subheader("Mapa de Calor Clínico")

    heat_df = patient_obs.pivot_table(
        index="created_at",
        columns="code",
        values="value_num"
    )

    fig_heat = px.imshow(
        heat_df,
        aspect="auto",
        title="Intensidad de Signos Vitales"
    )

    st.plotly_chart(fig_heat, use_container_width=True)

# ==========================
# TABLA RESUMEN
# ==========================
if not patient_obs.empty:

    st.subheader("Resumen de Observaciones")

    cols = [
        c for c in 
        ["created_at", "code", "value", "value_num", "outlier"]
        if c in patient_obs.columns
    ]

    styled_df = patient_obs[cols].sort_values(
        "created_at",
        ascending=False
    )

    def highlight_row(row):
        if "outlier" in row and row["outlier"] == True:
            return ["color: red; font-weight: bold"] * len(row)
        return [""] * len(row)

    styled = styled_df.style.apply(highlight_row, axis=1)

    if "outlier" in styled_df.columns:
        styled = styled.hide(axis="columns", subset=["outlier"])

    st.dataframe(styled, use_container_width=True)

else:
    st.info("No hay datos para mostrar en el resumen.")