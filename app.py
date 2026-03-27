import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuración de Estilo y Página
st.set_page_config(page_title="Recaall Analytics", layout="wide", initial_sidebar_state="expanded")

# Diseño elegante con CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# 2. Función de Procesamiento (Lógica de Datos)
def procesar_archivo(file):
    try:
        # Detectamos el separador (tu archivo usa ';')
        df = pd.read_csv(file, sep=';')
        
        # Limpieza de fechas y creación de columna 'Hora'
        df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True)
        df['hora'] = df['datetime'].dt.hour
        
        # Lógica de conversión (Venta)
        # Basado en tu muestra: "Conecta - efectivo" es el éxito
        df['es_venta'] = df['GES_descripcion_1'].str.contains('efectivo', case=False, na=False).astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error al procesar el formato del archivo: {e}")
        return None

# 3. BARRA LATERAL (Apartado de Carga)
with st.sidebar:
    st.image("https://via.placeholder.com/150x50?text=RECAALL", use_column_width=True) # Aquí podrías poner tu logo
    st.header("📂 Carga de Datos")
    uploaded_file = st.file_uploader("Sube tu archivo .csv de gestión", type=["csv"])
    st.info("Sube el archivo resultante de la campaña para analizar.")

# 4. CUERPO PRINCIPAL
if uploaded_file is not None:
    df = procesar_archivo(uploaded_file)
    
    if df is not None:
        st.title("📊 Dashboard de Gestión en Tiempo Real")
        
        # Filtros dinámicos
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            campanas = st.multiselect("Filtrar Campaña", df['GES_nombre_campana_gestion'].unique(), default=df['GES_nombre_campana_gestion'].unique())
        with col_f2:
            ejecutivos = st.multiselect("Filtrar Ejecutivo", df['GES_username_recurso'].unique())

        # Aplicación de filtros
        df_filt = df[df['GES_nombre_campana_gestion'].isin(campanas)]
        if ejecutivos:
            df_filt = df_filt[df_filt['GES_username_recurso'].isin(ejecutivos)]

        # METRICAS ELEGANTES
        m1, m2, m3, m4 = st.columns(4)
        total_gestiones = len(df_filt)
        ventas = df_filt['es_venta'].sum()
        conv = (ventas / total_gestiones * 100) if total_gestiones > 0 else 0
        
        m1.metric("Total Llamados", f"{total_gestiones:,}")
        m2.metric("Ventas (Efectivo)", f"{ventas:,}")
        m3.metric("% Conversión", f"{conv:.2f}%")
        m4.metric("Ejecutivos Activos", df_filt['GES_username_recurso'].nunique())

        st.markdown("---")

        # GRÁFICOS DINÁMICOS
        c1, c2 = st.columns([2, 1])

        with c1:
            st.subheader("Ventas vs Volumen por Hora")
            hourly_data = df_filt.groupby('hora').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
            fig_hora = px.bar(hourly_data, x='hora', y=['Llamados', 'Ventas'], 
                              barmode='group', template="plotly_dark",
                              color_discrete_sequence=['#1f77b4', '#00ff88'])
            st.plotly_chart(fig_hora, use_container_width=True)

        with c2:
            st.subheader("Top Motivos No Venta")
            no_ventas = df_filt[df_filt['es_venta'] == 0]['GES_descripcion_2'].value_counts().head(8)
            fig_pie = px.pie(values=no_ventas.values, names=no_ventas.index, 
                             hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

        # TABLA DE DETALLE POR EJECUTIVO
        st.subheader("Ranking de Eficiencia por Ejecutivo")
        ranking = df_filt.groupby('GES_username_recurso').agg(
            Llamados=('es_venta', 'count'),
            Ventas=('es_venta', 'sum')
        ).reset_index()
        ranking['% Conv'] = (ranking['Ventas'] / ranking['Llamados'] * 100).round(2)
        st.dataframe(ranking.sort_values(by='% Conv', ascending=False), use_container_width=True, hide_index=True)

else:
    # Pantalla de bienvenida cuando no hay archivo
    st.title("👋 Bienvenido al Analizador de Recaall")
    st.info("Por favor, sube un archivo CSV en la barra lateral para comenzar el análisis.")
    st.image("https://img.freepik.com/free-vector/data-report-concept-illustration_114360-883.jpg", width=400)
