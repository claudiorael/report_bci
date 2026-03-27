import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import google.generativeai as genai
import datetime

# --- CONFIGURACIÓN DE PÁGINA (TEMA CLARO) ---
st.set_page_config(page_title="Dashboard Recaall", layout="wide", initial_sidebar_state="expanded")

# CSS mínimo para forzar un fondo blanco/claro y texto oscuro
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
        
        # Limpieza de tiempos y creación de columnas temporales
        df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True)
        df['Hora'] = df['datetime'].dt.hour
        df['Día'] = df['datetime'].dt.date
        df['Semana'] = df['datetime'].dt.isocalendar().week
        
        # REGLA EXACTA: Solo contabiliza cuando dice exactamente "venta" (536 registros)
        df['es_venta'] = (df['GES_descripcion_3'].fillna('').str.strip().str.lower() == 'venta').astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error en el formato del archivo subido: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Carga de Datos")
    archivo_subido = st.file_uploader("Sube tu archivo BCI (.csv)", type=["csv"])
    
    st.divider()
    st.header("🤖 Asistente Gemini")
    api_key = st.text_input("API Key de Gemini", type="password")
    if api_key:
        genai.configure(api_key=api_key)

# --- CUERPO PRINCIPAL ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📊 Dashboard de Gestión de Ventas")
        
        # Filtros y Botón de Excel
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

        # --- MÉTRICAS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Llamados", len(df_final))
        m2.metric("Ventas Totales", df_final['es_venta'].sum()) 
        t_conv = (df_final['es_venta'].sum()/len(df_final)*100 if len(df_final)>0 else 0)
        m3.metric("Tasa de Conversión", f"{t_conv:.2f}%")
        m4.metric("Días Operativos", df_final['Día'].nunique())

        st.markdown("---")

        # --- GRÁFICO ORIGINAL (PRIMERA INTERFAZ) ---
        st.subheader("Desempeño Operativo")
        agrupacion_temporal = st.radio("Ver gráfico por:", ["Hora", "Día", "Semana"], horizontal=True)
        
        # Preparamos los datos según la selección (Hora, Día o Semana)
        resumen_temp = df_final.groupby(agrupacion_temporal).agg(
            Llamados=('es_venta', 'count'), 
            Ventas=('es_venta', 'sum')
        ).reset_index()
        
        # Convertimos a texto para que el gráfico no distorsione el eje X
        resumen_temp[agrupacion_temporal] = resumen_temp[agrupacion_temporal].astype(str)

        # Volvemos al gráfico de barras agrupadas con los colores azul y rojo originales
        fig_barras = px.bar(resumen_temp, x=agrupacion_temporal, y=['Llamados', 'Ventas'], 
                            barmode='group', title=f"Llamados vs Ventas por {agrupacion_temporal}",
                            labels={'value': 'Cantidad', agrupacion_temporal: agrupacion_temporal},
                            color_discrete_sequence=['#636EFA', '#EF553B'])
        
        fig_barras.update_layout(paper_bgcolor="white", plot_bgcolor="white")
        st.plotly_chart(fig_barras, use_container_width=True)

        # --- TABLA DE DETALLE (PRIMERA INTERFAZ) ---
        st.subheader("Detalle de Conversión por Ejecutivo")
        ranking = df_final.groupby('GES_username_recurso').agg(
            Llamados=('es_venta', 'count'),
            Ventas=('es_venta', 'sum')
        ).reset_index()
        ranking['Eficiencia %'] = (ranking['Ventas'] / ranking['Llamados'] * 100).round(2)
        ranking = ranking.sort_values(by='Ventas', ascending=False)
        
        st.dataframe(ranking, use_container_width=True, hide_index=True)

        # --- CONCLUSIONES AUTOMÁTICAS ---
        st.markdown("---")
        st.subheader("📝 Diagnóstico Rápido")
        for camp in campanas:
            df_camp = df_final[df_final['GES_nombre_campana_gestion'] == camp]
            if not df_camp.empty:
                t_llamados = len(df_camp)
                t_ventas = df_camp['es_venta'].sum()
                mejor_ejecutivo = df_camp.groupby('GES_username_recurso')['es_venta'].sum().idxmax() if t_ventas > 0 else "N/A"
                st.info(f"**Campaña {camp}:** {t_llamados} llamados generaron {t_ventas} ventas. Ejecutivo con más cierres: {mejor_ejecutivo}.")

        # --- CHAT GEMINI ---
        st.markdown("---")
        st.subheader("🤖 Consultar a Gemini")
        if api_key:
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
            st.warning("Ingresa tu API Key en la barra lateral para usar el chat.")

else:
    st.title("📊 Dashboard de Gestión BCI")
    st.info("Por favor, sube un archivo CSV en la barra lateral para visualizar los datos.")
