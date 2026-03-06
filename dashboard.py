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
# LOGIN SEGURO
# ==========================

if "auth" not in st.session_state:
    st.session_state.auth = False

with st.sidebar.form("login_form"):
    st.header("Login")

    access_key_input = st.text_input("Access Key", type="password")
    permission_key_input = st.text_input("Permission Key", type="password")

    submitted = st.form_submit_button("Ingresar")

    if submitted:
        st.session_state.access_key = access_key_input
        st.session_state.permission_key = permission_key_input
        st.session_state.auth = True
        st.rerun()

if not st.session_state.auth:
    st.stop()

access_key = st.session_state.access_key
permission_key = st.session_state.permission_key

HEADERS = {
    "x-access-key": access_key,
    "x-permission-key": permission_key
}

# ==========================
# FUNCIONES API
# ==========================

@st.cache_data(ttl=15)
def fetch_patients(access_key, permission_key):
    headers = {
        "x-access-key": access_key,
        "x-permission-key": permission_key
    }

    r = requests.get(
        f"{API_URL}/fhir/Patient?limit=100&offset=0",
        headers=headers
    )

    if r.status_code != 200:
        return None

    return pd.DataFrame(r.json()["data"])


@st.cache_data(ttl=15)
def fetch_observations(access_key, permission_key):

    headers = {
        "x-access-key": access_key,
        "x-permission-key": permission_key
    }

    r = requests.get(
        f"{API_URL}/fhir/Observation?limit=500&offset=0",
        headers=headers
    )

    if r.status_code != 200:
        return None, None

    data = r.json()

    obs_df = pd.DataFrame(data.get("data", []))
    alerts_df = pd.DataFrame(data.get("alerts", []))

    return obs_df, alerts_df


# ==========================
# CARGAR DATOS
# ==========================

patients_df = fetch_patients(access_key, permission_key)
obs_df, alerts_df = fetch_observations(access_key, permission_key)

if patients_df is None or patients_df.empty:
    st.error("No se pudieron cargar pacientes.")
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
# SELECCIÓN PACIENTE
# ==========================

if is_admin:

    st.subheader("Pacientes (Admin)")
    st.dataframe(patients_df[["id"]])

    selected_patient = st.selectbox(
        "Seleccionar Paciente",
        patients_df["id"]
    )


elif is_patient:

    selected_patient = patients_df.iloc[0]["id"]
    st.subheader(f"Paciente: {selected_patient}")


elif is_medico:

    st.subheader("Pacientes Registrados")

    display_cols = [
        c for c in
        ["id","given_name","family_name","gender","birth_date"]
        if c in patients_df.columns
    ]

    display_df = patients_df[display_cols].reset_index(drop=True)

    st.dataframe(display_df)

    idx = st.number_input(
        "Seleccione índice paciente",
        min_value=0,
        max_value=len(display_df)-1,
        step=1
    )

    selected_patient = display_df.iloc[idx]["id"]

# ==========================
# INFO PACIENTE
# ==========================

patient_info = patients_df[patients_df["id"] == selected_patient]

if not patient_info.empty:

    info = patient_info.iloc[0]

    st.markdown("### Información Paciente")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Nombre",
        f"{info.get('given_name','')} {info.get('family_name','')}"
    )

    col2.metric(
        "Genero",
        info.get("gender","N/A")
    )

    col3.metric(
        "Nacimiento",
        info.get("birth_date","N/A")
    )

# ==========================
# MEDICAL SUMMARY (SOLO MEDICO)
# ==========================

if is_medico:

    r = requests.get(
        f"{API_URL}/medical_summary/{selected_patient}",
        headers=HEADERS
    )

    if r.status_code == 200:

        summary = r.json()

        st.subheader("Resumen Médico")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Total Observaciones",
            summary.get("total_observations",0)
        )

        c2.metric(
            "Alertas",
            summary.get("alerts",0)
        )

        c3.metric(
            "Tipos Signos",
            summary.get("vital_types",0)
        )

# ==========================
# ALERTAS CLÍNICAS
# ==========================

if is_medico and alerts_df is not None and not alerts_df.empty:

    patient_alerts = alerts_df[
        alerts_df["patient_id"] == selected_patient
    ]

    if not patient_alerts.empty:

        st.error("⚠ ALERTAS CLINICAS")

        for _, a in patient_alerts.iterrows():

            st.warning(
                f"{a['code']} = {a['value']} → {a['message']}"
            )

# ==========================
# CREAR OBSERVACION
# ==========================

if is_medico or is_admin:

    st.subheader("Nueva Observación")

    with st.form("new_obs"):

        col1,col2 = st.columns(2)

        code = col1.selectbox(
            "Signo Vital",
            [
                "heart_rate",
                "temperature",
                "glucose",
                "platelets",
                "systolic_pressure",
                "diastolic_pressure"
            ]
        )

        value = col2.number_input("Valor",step=0.1)

        unit = st.text_input("Unidad")

        submit = st.form_submit_button("Guardar")

        if submit:

            impossible=False

            if code=="temperature" and value>45:
                impossible=True

            if code=="heart_rate" and value>250:
                impossible=True

            if code=="systolic_pressure" and value>350:
                impossible=True

            if impossible:
                st.error("Valor clínicamente imposible")

            else:

                payload={
                    "patient_id":selected_patient,
                    "code":code,
                    "value":value,
                    "unit":unit
                }

                r=requests.post(
                    f"{API_URL}/fhir/Observation",
                    headers=HEADERS,
                    json=payload
                )

                if r.status_code==200:
                    st.success("Observación creada")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(r.text)

# ==========================
# EDITAR OBSERVACION
# ==========================

if is_admin or is_medico:

    st.subheader("Editar Observación")

    obs_id = st.number_input("ID",min_value=1)

    new_value = st.number_input(
        "Nuevo Valor",
        step=0.1
    )

    if st.button("Actualizar Observación"):

        payload={"value":new_value}

        r=requests.put(
            f"{API_URL}/fhir/Observation/{obs_id}",
            headers=HEADERS,
            json=payload
        )

        if r.status_code==200:
            st.success("Observación actualizada")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(r.text)

# ==========================
# ELIMINAR OBSERVACION
# ==========================

if is_admin or is_medico:

    st.subheader("Eliminar Observación")

    delete_id = st.number_input(
        "ID eliminar",
        min_value=1
    )

    if st.button("Eliminar Observación"):

        r=requests.delete(
            f"{API_URL}/fhir/Observation/{delete_id}",
            headers=HEADERS
        )

        if r.status_code==200:
            st.success("Observación eliminada")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(r.text)

# ==========================
# CREAR PACIENTE
# ==========================

import uuid

if is_admin or is_medico:

    st.subheader("Crear Paciente")

    with st.form("create_patient"):

        col1, col2 = st.columns(2)

        given = col1.text_input("Nombre")
        family = col2.text_input("Apellido")

        col3, col4 = st.columns(2)

        gender = col3.selectbox(
            "Genero",
            ["male", "female", "other"]
        )

        birth = col4.text_input(
            "Nacimiento (YYYY-MM-DD)"
        )

        # ✅ Este campo debe estar dentro del form
        medical_summary = st.text_area("Medical Summary")

        submit = st.form_submit_button("Crear Paciente")

        if submit:

            if not given or not family or not birth:

                st.error("Todos los campos son obligatorios")

            else:

                # ✅ Generar ID y key automáticamente
                patient_id = f"pac-{uuid.uuid4().hex[:8]}"
                patient_key = uuid.uuid4().hex

                payload = {
                    "id": patient_id,
                    "given_name": given,
                    "family_name": family,
                    "gender": gender,
                    "birthDate": birth,
                    "medical_summary": medical_summary,
                    "patient_key": patient_key
                }

                r = requests.post(
                    f"{API_URL}/fhir/Patient",
                    headers=HEADERS,
                    json=payload
                )

                if r.status_code == 200:

                    st.success("Paciente creado correctamente")

                    st.cache_data.clear()
                    st.rerun()

                else:

                    st.error("Error al crear paciente")
                    st.write(r.status_code, r.text)

# ==========================
# EDITAR PACIENTE (ADMIN)
# ==========================

if is_admin:

    st.subheader("Editar Paciente")

    p_id = st.text_input("ID Paciente")

    new_name = st.text_input("Nuevo Nombre")

    new_last = st.text_input("Nuevo Apellido")

    if st.button("Actualizar Paciente"):

        payload={}

        if new_name:
            payload["given_name"]=new_name

        if new_last:
            payload["family_name"]=new_last

        r=requests.put(
            f"{API_URL}/fhir/Patient/{p_id}",
            headers=HEADERS,
            json=payload
        )

        if r.status_code==200:
            st.success("Paciente actualizado")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(r.text)

# ==========================
# ELIMINAR PACIENTE (ADMIN)
# ==========================

if is_admin:

    st.subheader("Eliminar Paciente")

    p_del = st.text_input("ID eliminar")

    if st.button("Eliminar Paciente"):

        r=requests.delete(
            f"{API_URL}/fhir/Patient/{p_del}",
            headers=HEADERS
        )

        if r.status_code==200:
            st.success("Paciente eliminado")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(r.text)

# ==========================
# FILTRAR OBSERVACIONES
# ==========================

if "total" in obs_df.columns:
    st.subheader("Conteo Observaciones")
    st.dataframe(obs_df)
    st.stop()

patient_obs = obs_df[
    obs_df["patient_id"]==selected_patient
].copy()

if patient_obs.empty:
    st.info("Sin observaciones")
    st.stop()

# ==========================
# LIMPIEZA
# ==========================

patient_obs["value_num"]=pd.to_numeric(
    patient_obs["value"],
    errors="coerce"
)

patient_obs["created_at"]=pd.to_datetime(
    patient_obs["created_at"]
)

# ==========================
# OUTLIERS
# ==========================

def is_outlier(v,c):

    if c=="temperature":
        return v<30 or v>45

    if c=="heart_rate":
        return v<30 or v>250

    if c=="systolic_pressure":
        return v<50 or v>300

    return False

patient_obs["outlier"]=patient_obs.apply(
    lambda r:is_outlier(
        r["value_num"],
        r["code"]
    ),
    axis=1
)

# ==========================
# GRAFICAS
# ==========================

st.subheader("Tendencias")

for code in patient_obs["code"].unique():

    df=patient_obs[
        patient_obs["code"]==code
    ].sort_values("created_at")

    fig=px.line(
        df,
        x="created_at",
        y="value_num",
        title=code,
        markers=True
    )

    st.plotly_chart(fig,use_container_width=True)

# ==========================
# HEATMAP MEDICO
# ==========================

if is_medico:

    st.subheader("Mapa Calor")

    heat_df=patient_obs.pivot_table(
        index="created_at",
        columns="code",
        values="value_num",
        aggfunc="mean"
    )

    fig=px.imshow(
        heat_df,
        aspect="auto"
    )

    st.plotly_chart(fig,use_container_width=True)

# ==========================
# TABLA RESUMEN
# ==========================

st.subheader("Resumen Observaciones")

cols=[
    c for c in
    ["created_at","code","value","value_num","outlier"]
    if c in patient_obs.columns
]

df=patient_obs[cols].sort_values(
    "created_at",
    ascending=False
)

def style(row):

    if row["outlier"]:
        return ["color:red;font-weight:bold"]*len(row)

    return [""]*len(row)

styled=df.style.apply(style,axis=1)

styled=styled.hide(axis="columns",subset=["outlier"])

st.dataframe(styled,use_container_width=True)