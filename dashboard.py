import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# ==========================
# LOGIN DE SEGURIDAD
# ==========================
st.title("Dashboard de Gestión Clínica")

with st.sidebar.form("login_form"):
    st.header("Login Médico")
    access_key = st.text_input("Access Key", type="password")
    permission_key = st.text_input("Permission Key", type="password")
    submitted = st.form_submit_button("Ingresar")

if not submitted:
    st.stop()  # No sigue hasta que se ingrese la API Key

# ==========================
# CONFIGURACION DE LA API
# ==========================
API_URL = "https://proyecto-salud-digital.onrender.com"
HEADERS = {
    "x-access-key": access_key,
    "x-permission-key": permission_key
}

# ==========================
# CARGA DE DATOS
# ==========================
@st.cache_data
def fetch_patients():
    resp = requests.get(f"{API_URL}/fhir/Patient?limit=100&offset=0", headers=HEADERS)
    if resp.status_code != 200:
        st.error(f"Error al cargar pacientes: {resp.text}")
        return pd.DataFrame()
    data = resp.json()["data"]
    return pd.DataFrame(data)

@st.cache_data
def fetch_observations():
    resp = requests.get(f"{API_URL}/fhir/Observation?limit=500&offset=0", headers=HEADERS)
    if resp.status_code != 200:
        st.error(f"Error al cargar observaciones: {resp.text}")
        return pd.DataFrame()
    data = resp.json()["data"]
    return pd.DataFrame(data)

patients_df = fetch_patients()
obs_df = fetch_observations()

if patients_df.empty or obs_df.empty:
    st.stop()

# ==========================
# SELECCION DE PACIENTE
# ==========================
patient_options = patients_df["id"].tolist()
selected_patient = st.selectbox("Seleccione un paciente", patient_options)

patient_obs = obs_df[obs_df["patient_id"] == selected_patient]

if patient_obs.empty:
    st.info("No hay observaciones registradas para este paciente.")
    st.stop()

# ==========================
# VALIDACION DE OUTLIERS
# ==========================
def highlight_outliers(value, code):
    # Ejemplo: Temperatura > 45°C, Presión arterial muy alta (>300 mmHg)
    try:
        val = float(value)
    except:
        return ""
    if code == "TEMP" and (val < 30 or val > 45):
        return "color: red; font-weight: bold"
    if code == "BP" and (val > 300 or val < 30):
        return "color: red; font-weight: bold"
    return ""

# Convertimos valores numéricos si es posible
def safe_float(x):
    try:
        return float(x)
    except:
        return None

patient_obs["value_num"] = patient_obs["value"].apply(safe_float)

# Creamos columna de estilos
patient_obs["style"] = patient_obs.apply(lambda row: highlight_outliers(row["value_num"], row["code"]), axis=1)

# ==========================
# GRAFICAS DINAMICAS
# ==========================
st.subheader("Tendencias de Signos Vitales")
for code in patient_obs["code"].unique():
    df_code = patient_obs[patient_obs["code"] == code].sort_values("created_at")
    df_code = df_code.dropna(subset=["value_num"])
    if df_code.empty:
        continue

    fig = px.line(df_code, x="created_at", y="value_num", title=f"{code} en el tiempo")

    # Marcar puntos fuera de rango
    outliers = df_code[(df_code["value_num"] > 45) | (df_code["value_num"] < 30)]
    if not outliers.empty:
        fig.add_scatter(
            x=outliers["created_at"], 
            y=outliers["value_num"],
            mode="markers", 
            marker=dict(color="red", size=10),
            name="Outlier"
        )
    st.plotly_chart(fig, use_container_width=True)

# ==========================
# TABLA RESUMEN CON ALERTAS
# ==========================
st.subheader("Resumen de Observaciones")

# Aplicamos estilos a la columna 'value_num'
def style_value_column(row):
    return [""] * len(row) if pd.isna(row["value_num"]) else [row["style"] if col == "value_num" else "" for col in row.index]

st.dataframe(patient_obs.style.apply(style_value_column, axis=1))