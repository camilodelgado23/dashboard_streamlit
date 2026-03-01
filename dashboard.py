import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

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
    try:
        resp = requests.get(f"{API_URL}/fhir/Patient?limit=100&offset=0", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()["data"]
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al cargar pacientes: {e}")
        return pd.DataFrame()

@st.cache_data
def fetch_observations():
    try:
        resp = requests.get(f"{API_URL}/fhir/Observation?limit=500&offset=0", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()["data"]
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al cargar observaciones: {e}")
        return pd.DataFrame()

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
    if code.upper() == "TEMP" and (value is not None) and (value < 30 or value > 45):
        return "color: red; font-weight: bold"
    if code.upper() == "BP" and (value is not None) and (value > 300 or value < 30):
        return "color: red; font-weight: bold"
    return ""

def safe_float(x):
    try:
        return float(x)
    except:
        return None

patient_obs["value_num"] = patient_obs["value"].apply(safe_float)

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
        fig.add_scatter(x=outliers["created_at"], y=outliers["value_num"],
                        mode="markers", marker=dict(color="red", size=10),
                        name="Outlier")
    st.plotly_chart(fig, use_container_width=True)

# ==========================
# TABLA RESUMEN CON ALERTAS
# ==========================
st.subheader("Resumen de Observaciones")
def style_row(row):
    return [highlight_outliers(v, c) for v, c in zip(row["value_num"], row["code"])]

st.dataframe(patient_obs.style.apply(style_row, axis=1))