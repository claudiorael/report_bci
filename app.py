import streamlit as st
import pandas as pd
import plotly.express as px
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
    .metric-small { font-size: 1.2rem; font-weight: bold; color: #0F52BA; background-color: #F0F2F6; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 15px;}
    </style>
    """, unsafe_allow_html=True)

# --- PROCESAMIENTO DE DATOS OPTIMIZADO ---
@st.cache_data
def procesar_datos(file):
    try:
        df = pd.read_csv(file, sep=';')
        
        # Lectura flexible y limpieza de fechas corruptas
        df['datetime'] = pd.to_datetime(df['GES_fecha_creacion'] + ' ' + df['GES_hora_min_creacion'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['datetime'])
        
        df['Hora'] = df['datetime'].dt.hour
        df['Día'] = df['datetime'].dt.date.astype(str) 
        df['Semana'] = df['datetime'].dt.isocalendar().week
        
        # Filtro estricto para las ventas
        df['es_venta'] = (df['GES_descripcion_3'].fillna('').str.strip().str.lower() == 'venta').astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error en el formato del archivo subido: {e}")
        return None

# --- CACHÉ PARA EXCEL ---
@st.cache_data
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Filtrado')
    return output.getvalue()

# --- CONFIGURACIÓN DE IA (SECRETS EN LA NUBE) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    ia_activa = True
except Exception:
    ia_activa = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Carga de Datos")
    archivo_subido = st.file_uploader("Sube tu archivo BCI (.csv)", type=["csv"])
    
    st.divider()
    if ia_activa:
        st.success("🤖 Asistente IA Conectado")
    else:
        st.error("⚠️ Asistente IA Desconectado (Revisa los Secrets en Streamlit Cloud)")

# --- CUERPO PRINCIPAL ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📊 Dashboard de Gestión de Ventas")
        
        # Filtros y Excel
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            campanas = st.multiselect("Campaña", df['GES_nombre_campana_gestion'].unique(), default=df['GES_nombre_campana_gestion'].unique())
        with c_f2:
            ejecutivos = st.multiselect("Ejecutivo", df['GES_username_recurso'].unique())
        with c_f3:
            df_final = df[df['GES_nombre_campana_gestion'].isin(campanas)]
            if ejecutivos:
                df_final = df_final[df_final['GES_username_recurso'].isin(ejecutivos)]
            
            excel_data = generar_excel(df_final)
            st.write("##") 
            st.download_button(
                label="📥 Descargar a Excel",
                data=excel_data,
                file_name=f"reporte_recaall_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("---")

        # Métricas Cabecera
        m1, m2, m3, m4 = st.columns(4)
        total_llamados = len(df_final)
        total_ventas = df_final['es_venta'].sum()
        
        m1.metric("Total Llamados", total_llamados)
        m2.metric("Ventas Totales", total_ventas) 
        t_conv = (total_ventas / total_llamados * 100) if total_llamados > 0 else 0
        m3.metric("Tasa de Conversión", f"{t_conv:.2f}%")
        m4.metric("Días Operativos", df_final['Día'].nunique())

        st.markdown("---")

        # --- GRÁFICO DE DESEMPEÑO ---
        st.subheader("Desempeño Operativo (Volumen y Éxito)")
        
        vista = st.radio("Selecciona el nivel de detalle:", ["Resumen General por Día", "Detalle por Hora (Filtrar por Día)"], horizontal=True)
        
        fig_barras = None
        resumen_temp = None

        if vista == "Resumen General por Día":
            st.markdown(f"<div class='metric-small'>Total de ventas en la selección: {total_ventas}</div>", unsafe_allow_html=True)
            
            resumen_temp = df_final.groupby('Día').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
            resumen_temp['Día'] = resumen_temp['Día'].astype(str)
            resumen_temp['% Conv'] = (resumen_temp['Ventas'] / resumen_temp['Llamados'] * 100).fillna(0).round(1)
            resumen_temp['Etiqueta'] = resumen_temp['% Conv'].astype(str) + '%'
            
            fig_barras = px.bar(
                resumen_temp, x='Día', y='Llamados', text='Etiqueta',
                title="Volumen de Gestiones y Porcentaje de Conversión por Día",
                labels={'Llamados': 'Total Llamados', 'Día': 'Fecha'},
                color_discrete_sequence=['#CED4DA'], 
                hover_data={'Ventas': True, '% Conv': True, 'Etiqueta': False}
            )
            
        else: 
            dias_disponibles = sorted(df_final['Día'].unique())
            
            if len(dias_disponibles) > 0:
                dia_seleccionado = st.selectbox("📅 Selecciona un día específico:", dias_disponibles)
                df_dia = df_final[df_final['Día'] == dia_seleccionado]
                
                ventas_del_dia = df_dia['es_venta'].sum()
                st.markdown(f"<div class='metric-small'>Ventas totales logradas el {dia_seleccionado}: {ventas_del_dia}</div>", unsafe_allow_html=True)
                
                resumen_temp = df_dia.groupby('Hora').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
                resumen_temp['Hora'] = resumen_temp['Hora'].astype(str) + ":00" 
                
                resumen_temp['% Conv'] = (resumen_temp['Ventas'] / resumen_temp['Llamados'] * 100).fillna(0).round(1)
                resumen_temp['Etiqueta'] = resumen_temp['% Conv'].astype(str) + '%'
                
                fig_barras = px.bar(
                    resumen_temp, x='Hora', y='Llamados', text='Etiqueta',
                    title=f"Volumen y Conversión por Hora (Día: {dia_seleccionado})",
                    labels={'Llamados': 'Total Llamados', 'Hora': 'Franja Horaria'},
                    color_discrete_sequence=['#CED4DA'], 
                    hover_data={'Ventas': True, '% Conv': True, 'Etiqueta': False}
                )
            else:
                st.warning("No hay datos disponibles para la selección actual.")

        if fig_barras is not None:
            fig_barras.update_traces(textposition='auto', textfont=dict(size=14, color='#212529', family="Arial Black"))
            fig_barras.update_layout(paper_bgcolor="white", plot_bgcolor="white", hovermode="x unified")
            st.plotly_chart(fig_barras, use_container_width=True)

        # --- SECCIÓN: ANÁLISIS DE FUGAS Y CONTACTABILIDAD ---
        st.markdown("---")
        st.subheader("🛑 Análisis de Fugas y Contactabilidad")
        
        df_no_ventas = df_final[df_final['es_venta'] == 0]
        
        col_fuga1, col_fuga2 = st.columns(2)
        
        with col_fuga1:
            # Contactabilidad Estricta
            contactos_efectivos = df_final['GES_descripcion_1'].fillna('').str.startswith('Conecta').sum()
            tasa_cont = (contactos_efectivos / total_llamados * 100) if total_llamados > 0 else 0
            
            data_pie = pd.DataFrame({
                'Estado': ['Contacto Efectivo', 'Sin Contacto / Otros'],
                'Cantidad': [contactos_efectivos, total_llamados - contactos_efectivos]
            })
            
            fig_pie_cont = px.pie(
                data_pie, values='Cantidad', names='Estado',
                hole=0.6, title="Nivel de Contactabilidad",
                color='Estado',
                color_discrete_map={'Contacto Efectivo': '#636EFA', 'Sin Contacto / Otros': '#CED4DA'}
            )
            fig_pie_cont.update_layout(
                showlegend=True, 
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                paper_bgcolor="white", plot_bgcolor="white", margin=dict(t=30, b=0, l=0, r=0)
            )
            fig_pie_cont.add_annotation(text=f"{tasa_cont:.1f}%", x=0.5, y=0.5, showarrow=False, font_size=20, font_color='#212529')
            st.plotly_chart(fig_pie_cont, use_container_width=True)

        with col_fuga2:
            # Top Motivos No Venta
            if not df_no_ventas.empty:
                motivos_nv = df_no_ventas['GES_descripcion_2'].fillna('Sin Especificar').value_counts().reset_index().head(10)
                motivos_nv.columns = ['Motivo', 'Cantidad']
                
                fig_nv = px.bar(
                    motivos_nv, x='Cantidad', y='Motivo', orientation='h',
                    title="Top Motivos No Venta", text='Cantidad',
                    color_discrete_sequence=['#EF553B']
                )
                fig_nv.update_traces(textposition='outside', textfont=dict(size=11, color='#212529'))
                fig_nv.update_layout(yaxis={'categoryorder':'total ascending'}, paper_bgcolor="white", plot_bgcolor="white", margin=dict(l=0, r=20, t=30, b=0))
                st.plotly_chart(fig_nv, use_container_width=True)

        # --- TABLA Y RENDIMIENTO DEL EJECUTIVO ---
        st.markdown("---")
        st.subheader("👨‍💼 Análisis de Rendimiento de Ejecutivos")
        
        ranking = df_final.groupby('GES_username_recurso').agg(
            Llamados=('es_venta', 'count'),
            Ventas=('es_venta', 'sum')
        ).reset_index()
        ranking['Eficiencia %'] = (ranking['Ventas'] / ranking['Llamados'] * 100).round(2)
        ranking = ranking.sort_values(by='Ventas', ascending=False)
        
        if not ranking.empty:
            promedio_equipo = ranking['Eficiencia %'].mean()
            lider = ranking.iloc[0]
            
            col_rend1, col_rend2 = st.columns(2)
            with col_rend1:
                st.success(f"🏆 **Alto Desempeño:** **{lider['GES_username_recurso']}** lidera las ventas con un total de **{lider['Ventas']} cierres** y una eficiencia del **
