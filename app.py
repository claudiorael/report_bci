import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import google.generativeai as genai
import datetime

# --- 1. CONFIGURACIÓN DE ESTILO RECAALL ---
st.set_page_config(page_title="Recaall Analytics - BCI", layout="wide", initial_sidebar_state="expanded")

# Estética limpia y profesional (Azul Recaall)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #31333F; }
    [data-testid="stSidebar"] { background-color: #F0F2F6; border-right: 1px solid #E6E6E9; }
    h1, h2, h3 { color: #0F52BA !important; }
    .stMetric { background-color: #F8F9FA; padding: 15px; border-radius: 10px; border: 1px solid #E6E6E9; }
    [data-testid="stMetricValue"] { color: #0F52BA !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE PROCESAMIENTO ---
@st.cache_data
def procesar_datos(file):
    try:
        # Lectura con separador punto y coma
        df = pd.read_csv(file, sep=';')
        
        # Limpieza de fechas y creación de columnas temporales
        df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['datetime'])
        
        df['Hora'] = df['datetime'].dt.hour
        df['Día'] = df['datetime'].dt.date.astype(str)
        
        # Lógica de negocio: ¿Qué es una venta?
        df['es_venta'] = (df['GES_descripcion_3'].fillna('').str.strip().str.lower() == 'venta').astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error procesando el CSV: {e}")
        return None

@st.cache_data
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data_Recaall')
    return output.getvalue()

# --- 3. CONEXIÓN CON GEMINI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    ia_activa = True
except Exception:
    ia_activa = False

# --- 4. INTERFAZ LATERAL ---
with st.sidebar:
    st.header("📂 Carga de Gestión")
    archivo_subido = st.file_uploader("Subir archivo CSV (Formato BCI)", type=["csv"])
    st.divider()
    if ia_activa:
        st.success("🤖 Analista IA Conectado")
    else:
        st.warning("⚠️ IA Desconectada (Revisa los Secrets)")

# --- 5. CUERPO DEL DASHBOARD ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📊 Control de Gestión Recaall - BCI")
        
        # Filtros de usuario
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            campanas = st.multiselect("Campaña", df['GES_nombre_campana_gestion'].unique(), default=df['GES_nombre_campana_gestion'].unique())
        with col_f2:
            ejecutivos = st.multiselect("Ejecutivos Específicos", df['GES_username_recurso'].unique())

        # Aplicación de filtros
        df_final = df[df['GES_nombre_campana_gestion'].isin(campanas)]
        if ejecutivos:
            df_final = df_final[df_final['GES_username_recurso'].isin(ejecutivos)]

        # KPIs Principales
        m1, m2, m3, m4 = st.columns(4)
        total_gestiones = len(df_final)
        total_ventas = df_final['es_venta'].sum()
        tasa_conv = (total_ventas / total_gestiones * 100) if total_gestiones > 0 else 0
        
        m1.metric("Gestiones Totales", total_gestiones)
        m2.metric("Ventas Logradas", total_ventas)
        m3.metric("% Conversión", f"{tasa_conv:.2f}%")
        m4.metric("Días de Operación", df_final['Día'].nunique())

        st.divider()

        # Visualizaciones
        col_chart1, col_chart2 = st.columns([2, 1])
        
        with col_chart1:
            st.subheader("Rendimiento por Bloque Horario")
            stats_hora = df_final.groupby('Hora').agg(Ventas=('es_venta', 'sum')).reset_index()
            fig_h = px.bar(stats_hora, x='Hora', y='Ventas', color_discrete_sequence=['#0F52BA'])
            st.plotly_chart(fig_h, use_container_width=True)

        with col_chart2:
            st.subheader("Estado de Contactabilidad")
            cont_stats = df_final['GES_descripcion_1'].value_counts().head(5)
            fig_p = px.pie(values=cont_stats.values, names=cont_stats.index, hole=0.4)
            st.plotly_chart(fig_p, use_container_width=True)

        # Tabla de Ejecutivos y Exportación
        st.subheader("👨‍💼 Desempeño por Ejecutivo")
        ranking = df_final.groupby('GES_username_recurso').agg(
            Llamados=('es_venta', 'count'),
            Ventas=('es_venta', 'sum')
        ).reset_index().sort_values(by='Ventas', ascending=False)
        st.dataframe(ranking, use_container_width=True, hide_index=True)
        
        st.download_button("📥 Descargar Reporte en Excel", generar_excel(df_final), 
                           "reporte_recaall_bci.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- 6. EL CEREBRO DE GEMINI (ANALISTA SENIOR) ---
        st.divider()
        st.subheader("🤖 Consultar a Gemini (Analista Senior)")
        
        if ia_activa:
            user_input = st.chat_input("Pregunta sobre horarios, tipificaciones o rendimiento...")
            if user_input:
                with st.chat_message("user"): st.write(user_input)
                
                # Preparamos la data "masticada" para que la IA sea 100% precisa
                h_data = df_final.groupby('Hora').agg(Llamados=('es_venta','count'), Ventas=('es_venta','sum')).reset_index()
                h_data['%_Conv'] = (h_data['Ventas']/h_data['Llamados']*100).round(1)
                
                tipificaciones = df_final['GES_descripcion_2'].value_counts().head(15).to_string()
                estados = df_final['GES_descripcion_1'].value_counts().head(10).to_string()

                contexto_ia = f"""
                Eres Claudio, Analista Senior de Recaall SpA. Analiza esta data de la campaña BCI:
                
                --- RENDIMIENTO POR HORA:
                {h_data.to_string(index=False)}
                
                --- TIPIFICACIONES (Motivos No Venta):
                {tipificaciones}
                
                --- ESTADOS DE LLAMADA (Contactabilidad):
                {estados}
                
                Pregunta del Gerente: {user_input}
                Responde como experto, detectando patrones horarios y motivos de fuga.
                """

                with st.chat_message("assistant"):
                    try:
                        # Selección automática de modelo
                        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        model_name = next((m for m in modelos if '1.5-flash' in m), modelos[0])
                        
                        gemini = genai.GenerativeModel(model_name)
                        res = gemini.generate_content(contexto_ia)
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"Error IA: {e}")
else:
    st.info("👋 Bienvenido, Claudio. Por favor sube el archivo CSV de gestión para comenzar el análisis.")
