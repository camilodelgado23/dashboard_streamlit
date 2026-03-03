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
@st.cache_data
def fetch_patients(access_key, permission_key):
    headers = {
        "x-access-key": access_key,
        "x-permission-key": permission_key
    }
    resp = requests.get(f"{API_URL}/fhir/Patient?limit=100&offset=0", headers=headers)
    if resp.status_code != 200:
        return None
    return pd.DataFrame(resp.json()["data"])


@st.cache_data
def fetch_observations(access_key, permission_key):
    headers = {
        "x-access-key": access_key,
        "x-permission-key": permission_key
    }
    resp = requests.get(f"{API_URL}/fhir/Observation?limit=500&offset=0", headers=headers)
    if resp.status_code != 200:
        return None
    return pd.DataFrame(resp.json()["data"])


# ==========================
# CARGA DATOS
# ==========================
patients_df = fetch_patients(access_key, permission_key)
obs_df = fetch_observations(access_key, permission_key)

if patients_df is None or patients_df.empty:
    st.error("No se pudieron cargar pacientes o no tienes permisos.")
    st.stop()

if obs_df is None:
    st.error("No se pudieron cargar observaciones.")
    st.stop()

# ==========================
# DETECTAR ROL
# ==========================
is_patient = len(patients_df) == 1

# ==========================
# SELECCION DE PACIENTE
# ==========================
if is_patient:
    selected_patient = patients_df.iloc[0]["id"]
    st.subheader(f"Paciente: {selected_patient}")
else:
    selected_patient = st.selectbox(
        "Seleccione un paciente",
        patients_df["id"].tolist()
    )

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
# FILTRAR OBSERVACIONES
# ==========================
patient_obs = obs_df[obs_df["patient_id"] == selected_patient].copy()

if patient_obs.empty:
    st.info("No hay observaciones registradas para este paciente.")
    st.stop()

# ==========================
# LIMPIEZA DATOS
# ==========================
def safe_float(x):
    try:
        return float(x)
    except:
        return None

patient_obs["value_num"] = patient_obs["value"].apply(safe_float)
patient_obs["created_at"] = pd.to_datetime(patient_obs["created_at"])

# ==========================
# REGLAS DE OUTLIERS
# ==========================
def is_outlier(value, code):
    if value is None:
        return False

    if code == "TEMP":
        return value < 30 or value > 45
    if code == "BP":
        return value < 30 or value > 300
    return False


patient_obs["outlier"] = patient_obs.apply(
    lambda row: is_outlier(row["value_num"], row["code"]),
    axis=1
)

# ==========================
# GRAFICAS
# ==========================
st.subheader("Tendencias de Signos Vitales")

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

    outliers = df_code[df_code["outlier"]]

    if not outliers.empty:
        fig.add_scatter(
            x=outliers["created_at"],
            y=outliers["value_num"],
            mode="markers",
            marker=dict(color="red", size=12),
            name="Outlier"
        )

    st.plotly_chart(fig, use_container_width=True)

# ==========================
# TABLA RESUMEN
# ==========================
st.subheader("Resumen de Observaciones")

def highlight_row(row):
    if row["outlier"]:
        return ["color: red; font-weight: bold"] * len(row)
    return [""] * len(row)

styled_df = patient_obs[
    ["created_at", "code", "value", "value_num"]
].sort_values("created_at", ascending=False)

st.dataframe(styled_df.style.apply(highlight_row, axis=1))