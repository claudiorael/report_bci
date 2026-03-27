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
        st.error("⚠️ Asistente IA Desconectado (Falta API Key)")

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

        # --- GRÁFICO DE DESEMPEÑO (BARRAS GRISES CON TEXTO) ---
        st.subheader("Desempeño Operativo (Volumen y Éxito)")
        
        vista = st.radio("Selecciona el nivel de detalle:", ["Resumen General por Día", "Detalle por Hora (Filtrar por Día)"], horizontal=True)
        
        fig_barras = None
        resumen_temp = None

        if vista == "Resumen General por Día":
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


        # --- NUEVA SECCIÓN: ANÁLISIS DE FUGAS (NO VENTAS) ---
        st.markdown("---")
        st.subheader("🛑 Análisis de Fugas (Motivos de No Venta)")
        
        df_no_ventas = df_final[df_final['es_venta'] == 0]
        
        if not df_no_ventas.empty:
            col_fuga1, col_fuga2 = st.columns([2, 1])
            
            with col_fuga1:
                # Top 10 motivos de rechazo
                motivos = df_no_ventas['GES_descripcion_2'].fillna('Sin Especificar').value_counts().reset_index()
                motivos.columns = ['Motivo', 'Cantidad']
                motivos_top = motivos.head(10)
                
                fig_fugas = px.bar(
                    motivos_top, x='Cantidad', y='Motivo', orientation='h',
                    title="Top 10 Razones de Falla",
                    text='Cantidad',
                    color_discrete_sequence=['#EF553B'] # Rojo para destacar que es un bloqueo
                )
                fig_fugas.update_traces(textposition='outside', textfont=dict(size=12, color='#212529'))
                fig_fugas.update_layout(
                    yaxis={'categoryorder':'total ascending'}, # Ordena para que el mayor quede arriba
                    paper_bgcolor="white", plot_bgcolor="white",
                    margin=dict(l=0, r=20, t=40, b=0)
                )
                st.plotly_chart(fig_fugas, use_container_width=True)
                
            with col_fuga2:
                # Tasa de Contactabilidad (Conecta vs No Conecta)
                st.markdown("#### Nivel de Contactabilidad")
                st.caption("Proporción de llamadas que lograron conexión real con un cliente.")
                
                # Buscamos la palabra "Conecta" en la descripción 1
                df_final['Contactó'] = df_final['GES_descripcion_1'].fillna('').str.contains('Conecta', case=False)
                contactabilidad = df_final['Contactó'].value_counts().reset_index()
                contactabilidad.columns = ['Conectó', 'Cantidad']
                contactabilidad['Estado'] = contactabilidad['Conectó'].apply(lambda x: 'Contacto Efectivo' if x else 'Sin Contacto')
                
                fig_pie_cont = px.pie(
                    contactabilidad, values='Cantidad', names='Estado',
                    hole=0.6,
                    color='Estado',
                    color_discrete_map={'Contacto Efectivo': '#636EFA', 'Sin Contacto': '#CED4DA'}
                )
                fig_pie_cont.update_layout(
                    showlegend=True, 
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                    paper_bgcolor="white", plot_bgcolor="white", 
                    margin=dict(t=10, b=0, l=0, r=0)
                )
                
                # Agregamos el % de contactabilidad en el centro del anillo
                tasa_cont = (df_final['Contactó'].sum() / len(df_final) * 100) if len(df_final) > 0 else 0
                fig_pie_cont.add_annotation(text=f"{tasa_cont:.1f}%", x=0.5, y=0.5, showarrow=False, font_size=24, font_color='#212529')
                
                st.plotly_chart(fig_pie_cont, use_container_width=True)
        else:
            st.success("No hay registros de llamadas sin venta en la selección actual.")


        # --- TABLA DE DETALLE ---
        st.markdown("---")
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
        if ia_activa:
            pregunta = st.chat_input("Ej: ¿Qué día tuvo la mejor conversión y por qué?")
            if pregunta:
                with st.chat_message("user"):
                    st.write(pregunta)
                
                if resumen_temp is not None:
                    contexto = f"Datos del gráfico en pantalla: \n{resumen_temp.to_string()}\nRanking Ejecutivos: \n{ranking.head(10).to_string()}\nPregunta: {pregunta}"
                else:
                    contexto = f"Ranking Ejecutivos: \n{ranking.head(10).to_string()}\nPregunta: {pregunta}"
                
                with st.chat_message("assistant"):
                    try:
                        modelo = genai.GenerativeModel('gemini-pro')
                        respuesta = modelo.generate_content(contexto)
                        st.write(respuesta.text)
                    except Exception as e:
                        st.error(f"Error conectando con Gemini: {e}")
        else:
            st.warning("Ingresa tu API Key en la configuración para usar el chat.")

else:
    st.title("📊 Dashboard de Gestión BCI")
    st.info("Por favor, sube un archivo CSV en la barra lateral para visualizar los datos.")
