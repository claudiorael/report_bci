import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
import google.generativeai as genai
import datetime

# --- CONFIGURACIÓN DE PÁGINA (TEMA CLARO) ---
st.set_page_config(page_title="Dashboard Recaall", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #31333F; }
    [data-testid="stSidebar"] { background-color: #F0F2F6; border-right: 1px solid #E6E6E9; }
    h1, h2, h3, h4, p, span, label { color: #31333F !important; }
    [data-testid="stMetricValue"] { color: #0F52BA !important; font-weight: bold; }
    .stAlert { background-color: #F8F9FA !important; border: 1px solid #DEE2E6 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- PROCESAMIENTO DE DATOS ---
@st.cache_data
def procesar_datos(file):
    try:
        df = pd.read_csv(file, sep=';')
        df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True)
        df['Hora'] = df['datetime'].dt.hour
        df['Día'] = df['datetime'].dt.date
        df['Semana'] = df['datetime'].dt.isocalendar().week
        df['es_venta'] = (df['GES_descripcion_3'].fillna('').str.strip().str.lower() == 'venta').astype(int)
        return df
    except Exception as e:
        st.error(f"Error en el formato del archivo subido: {e}")
        return None

# --- CONFIGURACIÓN DE IA (SECRETS) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    ia_activa = True
except KeyError:
    ia_activa = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Carga de Datos")
    archivo_subido = st.file_uploader("Sube tu archivo BCI (.csv)", type=["csv"])
    
    st.divider()
    if ia_activa:
        st.success("🤖 Asistente IA Conectado")
    else:
        st.warning("⚠️ Asistente IA Desconectado")

# --- CUERPO PRINCIPAL ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📊 Dashboard de Gestión de Ventas")
        
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            campanas = st.multiselect("Campaña", df['GES_nombre_campana_gestion'].unique(), default=df['GES_nombre_campana_gestion'].unique())
        with c_f2:
            ejecutivos = st.multiselect("Ejecutivo", df['GES_username_recurso'].unique())
        with c_f3:
            df_final = df[df['GES_nombre_campana_gestion'].isin(campanas)]
            if ejecutivos:
                df_final = df_final[df_final['GES_username_recurso'].isin(ejecutivos)]
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Reporte_Filtrado')
            
            st.write("##") 
            st.download_button(
                label="📥 Descargar a Excel",
                data=output.getvalue(),
                file_name=f"reporte_recaall_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("---")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Llamados", len(df_final))
        m2.metric("Ventas Totales", df_final['es_venta'].sum()) 
        t_conv = (df_final['es_venta'].sum()/len(df_final)*100 if len(df_final)>0 else 0)
        m3.metric("Tasa de Conversión", f"{t_conv:.2f}%")
        m4.metric("Días Operativos", df_final['Día'].nunique())

        st.markdown("---")

        # --- NUEVO GRÁFICO DE DOBLE EJE ---
        st.subheader("Desempeño Operativo")
        # Por defecto vendrá marcado en "Hora" como pediste
        agrupacion_temporal = st.radio("Ver gráfico por:", ["Hora", "Día", "Semana"], horizontal=True)
        
        resumen_temp = df_final.groupby(agrupacion_temporal).agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
        resumen_temp[agrupacion_temporal] = resumen_temp[agrupacion_temporal].astype(str)

        # Crear subplots con eje secundario activado
        fig_dual = make_subplots(specs=[[{"secondary_y": True}]])

        # Barra de Llamados (Eje Izquierdo)
        fig_dual.add_trace(
            go.Bar(x=resumen_temp[agrupacion_temporal], y=resumen_temp['Llamados'], name="Llamados", marker_color='#636EFA'),
            secondary_y=False,
        )

        # Línea de Ventas (Eje Derecho)
        fig_dual.add_trace(
            go.Scatter(x=resumen_temp[agrupacion_temporal], y=resumen_temp['Ventas'], name="Ventas", mode='lines+markers', marker_color='#EF553B', line=dict(width=3)),
            secondary_y=True,
        )

        # Ajustes visuales para dejarlo limpio y corporativo
        fig_dual.update_layout(
            title_text=f"Volumen vs Cierres Reales (Vista por {agrupacion_temporal})",
            paper_bgcolor="white",
            plot_bgcolor="white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # Ocultar las líneas de cuadrícula para que no se vea desordenado
        fig_dual.update_yaxes(title_text="Volumen Llamados", secondary_y=False, showgrid=False)
        fig_dual.update_yaxes(title_text="Total Ventas", secondary_y=True, showgrid=False)

        st.plotly_chart(fig_dual, use_container_width=True)
        # ------------------------------------

        st.subheader("Detalle de Conversión por Ejecutivo")
        ranking = df_final.groupby('GES_username_recurso').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
        ranking['Eficiencia %'] = (ranking['Ventas'] / ranking['Llamados'] * 100).round(2)
        ranking = ranking.sort_values(by='Ventas', ascending=False)
        st.dataframe(ranking, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("📝 Diagnóstico Rápido")
        for camp in campanas:
            df_camp = df_final[df_final['GES_nombre_campana_gestion'] == camp]
            if not df_camp.empty:
                t_llamados = len(df_camp)
                t_ventas = df_camp['es_venta'].sum()
                mejor_ejecutivo = df_camp.groupby('GES_username_recurso')['es_venta'].sum().idxmax() if t_ventas > 0 else "N/A"
                st.info(f"**Campaña {camp}:** {t_llamados} llamados generaron {t_ventas} ventas. Ejecutivo con más cierres: {mejor_ejecutivo}.")

        st.markdown("---")
        st.subheader("🤖 Consultar a Gemini")
        if ia_activa:
            pregunta = st.chat_input("Ej: ¿Qué día tuvo la mejor conversión y por qué?")
            if pregunta:
                with st.chat_message("user"):
                    st.write(pregunta)
                
                contexto = f"Datos actuales: \n{resumen_temp.to_string()}\nRanking: \n{ranking.head(10).to_string()}\nPregunta: {pregunta}"
                
                with st.chat_message("assistant"):
                    try:
                        modelo = genai.GenerativeModel('gemini-1.5-flash')
                        respuesta = modelo.generate_content(contexto)
                        st.write(respuesta.text)
                    except Exception as e:
                        st.error(f"Error conectando con Gemini: {e}")
        else:
            st.warning("La IA no está configurada. Contacta al administrador del sistema para agregar la API Key.")

else:
    st.title("📊 Dashboard de Gestión BCI")
    st.info("Por favor, sube un archivo CSV en la barra lateral para visualizar los datos.")
