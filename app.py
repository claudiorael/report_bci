import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Recaall con IA", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    div[data-testid="stMetricValue"] { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

# --- PROCESAMIENTO DE DATOS ---
@st.cache_data
def procesar_datos(file):
    try:
        df = pd.read_csv(file, sep=';')
        
        # Limpieza y creación de variables temporales
        df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True)
        df['Hora'] = df['datetime'].dt.hour
        df['Día'] = df['datetime'].dt.date
        # ISO week para la semana del año
        df['Semana'] = df['datetime'].dt.isocalendar().week 
        
        # NUEVA LÓGICA DE VENTA: Solo considera "venta" en GES_descripcion_3
        # Usamos fillna('') para evitar errores con celdas vacías y str.contains para ser flexibles con mayúsculas/minúsculas
        df['es_venta'] = df['GES_descripcion_3'].fillna('').str.lower().str.contains('venta').astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
        return None

# --- SIDEBAR Y CARGA ---
with st.sidebar:
    st.header("📂 Panel y Datos")
    archivo_subido = st.file_uploader("Cargar reporte (.csv)", type=["csv"])
    
    st.divider()
    st.header("🤖 Configuración de IA")
    api_key = st.text_input("Ingresa tu API Key de Gemini", type="password", help="Necesaria para consultar a la IA sobre los datos.")
    if api_key:
        genai.configure(api_key=api_key)

# --- CUERPO PRINCIPAL ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📈 Análisis de Campañas Recaall")
        
        # --- FILTROS ---
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            campanas = st.multiselect("Campaña", df['GES_nombre_campana_gestion'].unique(), default=df['GES_nombre_campana_gestion'].unique())
        with c_f2:
            ejecutivos = st.multiselect("Ejecutivo", df['GES_username_recurso'].unique())
        
        df_final = df[df['GES_nombre_campana_gestion'].isin(campanas)]
        if ejecutivos:
            df_final = df_final[df_final['GES_username_recurso'].isin(ejecutivos)]

        # --- MÉTRICAS ---
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Gestiones", f"{len(df_final):,}")
        m2.metric("Ventas Confirmadas", f"{df_final['es_venta'].sum():,}")
        conversion = (df_final['es_venta'].sum()/len(df_final)*100) if len(df_final)>0 else 0
        m3.metric("% Conversión", f"{conversion:.2f}%")

        st.markdown("---")

        # --- ANÁLISIS TEMPORAL DINÁMICO ---
        st.subheader("Tendencias de Venta")
        agrupacion = st.radio("Agrupar vista por:", ["Hora", "Día", "Semana"], horizontal=True)
        
        resumen_temp = df_final.groupby(agrupacion).agg(
            Gestiones=('es_venta', 'count'), 
            Ventas=('es_venta', 'sum')
        ).reset_index()

        fig_temp = px.line(resumen_temp, x=agrupacion, y=['Gestiones', 'Ventas'], 
                         markers=True, template="plotly_dark",
                         color_discrete_map={'Gestiones': '#4169E1', 'Ventas': '#00FF7F'})
        st.plotly_chart(fig_temp, use_container_width=True)

        # --- CONCLUSIONES POR CAMPAÑA ---
        st.markdown("---")
        st.subheader("📝 Análisis y Conclusiones por Campaña")
        
        for camp in campanas:
            df_camp = df_final[df_final['GES_nombre_campana_gestion'] == camp]
            if len(df_camp) > 0:
                t_llamados = len(df_camp)
                t_ventas = df_camp['es_venta'].sum()
                t_conv = (t_ventas / t_llamados * 100)
                mejor_ejecutivo = df_camp.groupby('GES_username_recurso')['es_venta'].sum().idxmax()
                max_ventas_ejec = df_camp.groupby('GES_username_recurso')['es_venta'].sum().max()
                
                st.info(f"""
                **Campaña: {camp}**
                * **Resumen de Esfuerzo:** Se realizaron **{t_llamados}** gestiones que resultaron en **{t_ventas}** ventas, logrando una efectividad del **{t_conv:.2f}%**.
                * **Rendimiento Humano:** El ejecutivo con mayor cantidad de cierres fue **{mejor_ejecutivo}** con {max_ventas_ejec} ventas.
                * **Diagnóstico:** {'La campaña muestra una conversión saludable.' if t_conv > 1.5 else 'Se detecta un alto volumen de gestiones con bajo cierre. Sugiere revisar los motivos de caída (GES_descripcion_2) o calibrar los guiones.'}
                """)

        # --- ASISTENTE IA (GEMINI) ---
        st.markdown("---")
        st.subheader("🤖 Consultor de IA Integrado")
        st.caption("Pregúntale a Gemini sobre los resultados actuales del dashboard.")

        if api_key:
            pregunta = st.chat_input("Ej: ¿Qué campaña tiene el mejor rendimiento y por qué?")
            if pregunta:
                # Mostrar el mensaje del usuario
                with st.chat_message("user"):
                    st.write(pregunta)
                
                # Crear un resumen de los datos filtrados para darle contexto a la IA
                contexto_datos = resumen_temp.to_string()
                resumen_ejecutivos = df_final.groupby('GES_username_recurso').agg(Ventas=('es_venta', 'sum'), Contactos=('es_venta', 'count')).to_string()
                
                prompt_ia = f"""
                Eres un analista de datos experto. Responde a la pregunta del usuario basándote EXCLUSIVAMENTE en el siguiente resumen de datos de un call center.
                Datos temporales:\n{contexto_datos}\n
                Datos por ejecutivo:\n{resumen_ejecutivos}\n
                Pregunta del usuario: {pregunta}
                """
                
                # Generar y mostrar respuesta
                with st.chat_message("assistant"):
                    try:
                        modelo = genai.GenerativeModel('gemini-1.5-flash')
                        respuesta = modelo.generate_content(prompt_ia)
                        st.write(respuesta.text)
                    except Exception as e:
                        st.error(f"Error al conectar con Gemini: {e}")
        else:
            st.warning("Introduce tu API Key de Gemini en el panel lateral para activar el chat.")

else:
    st.title("💼 Analítica Avanzada Recaall")
    st.info("Sube tu archivo CSV en la barra lateral para comenzar.")
