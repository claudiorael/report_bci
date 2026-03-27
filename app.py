import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuración de estilo
st.set_page_config(page_title="Recaall Analytics", layout="wide")

# CSS para mejorar la estética de las tarjetas
st.markdown("""
    <style>
    .metric-card {
        background-color: #262730;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_csv('BCI_gesCall_RECAALL_MI_20260326 (1).csv', sep=';')
    # Limpieza de fechas y horas
    df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True)
    df['hora'] = df['datetime'].dt.hour
    # Lógica de venta
    df['es_venta'] = df['GES_descripcion_1'].str.contains('efectivo', case=False, na=False).astype(int)
    return df

try:
    df = load_data()

    st.title("📊 Dashboard Comercial Recaall")
    st.markdown("---")

    # Filtros en columnas para que se vea más limpio
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        campanas = st.multiselect("Campañas", df['GES_nombre_campana_gestion'].unique(), default=df['GES_nombre_campana_gestion'].unique())
    with col_f2:
        ejecutivos = st.multiselect("Ejecutivos", df['GES_username_recurso'].unique())

    df_filt = df[df['GES_nombre_campana_gestion'].isin(campanas)]
    if ejecutivos:
        df_filt = df_filt[df_filt['GES_username_recurso'].isin(ejecutivos)]

    # Métricas principales
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Gestiones", f"{len(df_filt)}")
    m2.metric("Ventas", f"{df_filt['es_venta'].sum()}")
    m3.metric("% Conversión", f"{(df_filt['es_venta'].sum()/len(df_filt)*100):.2f}%")
    m4.metric("Prom. Llamadas/Hora", f"{df_filt.groupby('hora')['GES_nro_contacto'].count().mean():.1f}")

    st.markdown("### 📈 Rendimiento por Hora y Motivos")
    
    c1, c2 = st.columns([2, 1])

    with c1:
        # Gráfico de líneas dinámico
        hourly = df_filt.groupby('hora').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
        fig = px.area(hourly, x='hora', y=['Llamados', 'Ventas'], 
                      title="Flujo de Contactabilidad vs Cierre",
                      color_discrete_map={'Llamados': '#00CC96', 'Ventas': '#EF553B'},
                      template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        # Gráfico de torta de motivos de no venta
        no_ventas = df_filt[df_filt['es_venta'] == 0]['GES_descripcion_2'].value_counts().head(5)
        fig_pie = px.pie(values=no_ventas.values, names=no_ventas.index, 
                         title="Top 5 Motivos No Venta",
                         hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

except Exception as e:
    st.error(f"Error cargando datos: {e}")
