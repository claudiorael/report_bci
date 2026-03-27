import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import google.generativeai as genai
import datetime

# --- CONFIGURACIÓN DE PÁGINA Y NUEVA PALETA DE COLORES ---
# Definimos los colores corporativos analíticos
color_bg_main = "#111111"        # Fondo Oxford Negro/Gris muy oscuro
color_bg_card = "#1E1E1E"        # Fondo de tarjetas/sidebar (un poco más claro)
color_text = "#FAFAFA"           # Texto Blanco/Off-white
color_effort = "#3A86FF"         # Azul Real profesional (Llamados/Gestiones)
color_success = "#FB5607"        # Ámbar/Naranja cálido profesional (Ventas)
color_border = "#333333"         # Bordes suaves

st.set_page_config(page_title="Recaall Operations Analytics", layout="wide", initial_sidebar_state="expanded")

# --- CSS PERSONALIZADO (AQUÍ ESTÁ LA MAGIA VISUAL) ---
st.markdown(f"""
    <style>
    /* 1. Fondo principal y Sidebar */
    .stApp {{
        background-color: {color_bg_main};
        color: {color_text};
    }}
    [data-testid="stSidebar"] {{
        background-color: {color_bg_card};
        border-right: 1px solid {color_border};
    }}
    [data-testid="stHeader"] {{
        background-color: rgba(17, 17, 17, 0.8);
    }}
    
    /* 2. Títulos y Texto */
    h1, h2, h3, h4, .stSubheader, p {{
        color: {color_text} !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }}
    h1 {{ font-weight: 700; margin-bottom: 20px; }}
    
    /* 3. Estilización de Métricas */
    [data-testid="stMetricValue"] {{
        color: {color_success} !important;  /* Naranja para el éxito */
        font-weight: 700;
        font-size: 3rem !important;
    }}
    [data-testid="stMetricLabel"] p{{
        color: {color_text} !important;
        opacity: 0.8;
    }}
    /* Tarjeta contenedora de métrica */
    [data-testid="metric-container"] {{
        background-color: {color_bg_card};
        padding: 20px;
        border-radius: 12px;
        border: 1px solid {color_border};
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }}

    /* 4. Estilización de Cajas de Info/Mensajes (Conclusiones) */
    .stAlert {{
        background-color: {color_bg_card} !important;
        border: 1px solid {color_effort} !important;  /* Azul suave */
        color: {color_text} !important;
        border-radius: 10px;
        padding: 15px;
    }}
    .stAlert p, .stAlert li, .stAlert b{{
        color: {color_text} !important;
    }}

    /* 5. Otros componentes */
    div[data-testid="stRadio"] label p {{ color: {color_text} !important; }}
    div[data-testid="stChatInput"] input {{
        background-color: {color_bg_card} !important;
        border: 1px solid {color_border} !important;
        color: {color_text} !important;
    }}
    .stDataFrame table {{ border: 1px solid {color_border}; }}
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
        
        # REGLA: Venta solo desde GES_descripcion_3
        df['es_venta'] = df['GES_descripcion_3'].fillna('').str.lower().str.contains('venta').astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error en el formato del archivo subido: {e}")
        return None


# --- SIDEBAR (Apartado de Carga y Configuración IA) ---
with st.sidebar:
    st.image("
