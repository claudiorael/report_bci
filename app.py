import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Recaall Operations Analytics", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    div[data-testid="stMetricValue"] { color: #00ff88; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 10px; }
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
        st.error(f"Error en el formato: {e}")
        return None

# --- SIDEBAR (Apartado de Carga y Configuración IA) ---
with st.sidebar:
    st.header("📂 Panel de Control")
    archivo_subido = st.file_uploader("Cargar reporte BCI (.csv)", type=["csv"])
    st.info("Sube el archivo extraído de la plataforma para actualizar el dashboard.")
    
    st.divider()
    st.header("🤖 Integración Gemini")
    api_key = st.text_input("Ingresa tu API Key de Gemini", type="password")
    if api_key:
        genai.configure(api_key=api_key)

# --- CUERPO PRINCIPAL ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📈 Análisis de Conversión Recaall")
        
        # Filtros Superiores y Botón de Descarga
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
            
            st.download_button(
                label="📥 Descargar Selección (Excel)",
                data=output.getvalue(),
                file_name="reporte_filtrado_recaall.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.markdown("---")

        # Métricas de Impacto
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Gestiones", len(df_final))
        m2.metric("Ventas Totales", df_final['es_venta'].sum())
        m3.metric("% Conversión", f"{(df_final['es_venta'].sum()/len(df_final)*100 if len(df_final)>0 else 0):.2f}%")
        m4.metric("Ejecutivos Activos", df_final['GES_username_recurso'].nunique())

        st.markdown("---")

        # --- NUEVO: VISTA DE GRÁFICO POR DÍA (TENDENCIA) ---
        st.subheader("📅 Evolución Diaria de Resultados")
        tendencia_diaria = df_final.groupby('Día').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
        
        fig_linea = px.line(tendencia_diaria, x='Día', y=['Llamados', 'Ventas'], 
                            markers=True, template="plotly_dark",
                            color_discrete_map={'Llamados': '#4169E1', 'Ventas': '#00FF7F'},
                            labels={'value': 'Volumen', 'variable': 'Métrica'})
        
        # Ajustes visuales para que se vea más elegante
        fig_linea.update_layout(hovermode="x unified", xaxis_title="Fecha de Gestión", yaxis_title="Cantidad")
        st.plotly_chart(fig_linea, use_container_width=True)


        # --- OTROS GRÁFICOS DINÁMICOS ---
        st.markdown("### 📊 Distribución y Fugas")
        col_g1, col_g2 = st.columns([2, 1])

        with col_g1:
            st.markdown("#### Concentración Operativa")
            agrupacion_temporal = st.radio("Analizar concentración por:", ["Hora", "Semana"], horizontal=True)
            
            resumen_temp = df_final.groupby(agrupacion_temporal).agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
            resumen_temp[agrupacion_temporal] = resumen_temp[agrupacion_temporal].astype(str) 
            
            fig_bar = px.bar(resumen_temp, x=agrupacion_temporal, y=['Llamados', 'Ventas'], 
                             barmode='group', template="plotly_dark",
                             color_discrete_sequence=['#4169E1', '#00FF7F'],
                             labels={'value': 'Cantidad', 'variable': 'Tipo'})
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_g2:
            st.markdown("#### Motivos No Venta")
            motivos = df_final[df_final['es_venta'] == 0]['GES_descripcion_2'].value_counts().head(6)
            fig_pie = px.pie(values=motivos.values, names=motivos.index, hole=.4, template="plotly_dark")
            fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

        # Análisis y Conclusiones Automáticas
        st.markdown("---")
        st.subheader("📝 Análisis y Conclusiones por Campaña")
        for camp in campanas:
            df_camp = df_final[df_final['GES_nombre_campana_gestion'] == camp]
            if not df_camp.empty:
                t_llamados = len(df_camp)
                t_ventas = df_camp['es_venta'].sum()
                t_conv = (t_ventas / t_llamados * 100) if t_llamados > 0 else 0
                mejor_ejecutivo = df_camp.groupby('GES_username_recurso')['es_venta'].sum().idxmax() if t_ventas > 0 else "N/A"
                
                st.info(f"""
                **{camp}:** Se registraron **{t_llamados}** gestiones y **{t_ventas}** ventas, logrando una conversión de **{t_conv:.2f}%**. 
                Ejecutivo destacado en volumen de ventas: **{mejor_ejecutivo}**.
                """)

        # Tabla detallada por ejecutivo
        st.subheader("Detalle por Ejecutivo")
        ranking = df_final.groupby('GES_username_recurso').agg(
            Contactos=('es_venta', 'count'),
            Ventas=('es_venta', 'sum')
        ).sort_values(by='Ventas', ascending=False)
        st.table(ranking.head(10))

        # Apartado IA
        st.markdown("---")
        st.subheader("🤖 Consultar a Gemini")
        st.caption("Pregunta sobre los indicadores, días clave o rendimiento de ejecutivos en pantalla.")
        
        if api_key:
            pregunta = st.chat_input("Escribe tu consulta analítica aquí...")
            if pregunta:
                with st.chat_message("user"):
                    st.write(pregunta)
                
                contexto = f"""
                Responde de forma ejecutiva como experto en recursos humanos y análisis de datos. 
                Datos actuales filtrados:
                {resumen_temp.to_string()}
                Rendimiento de ejecutivos (Top 10):
                {ranking.head(10).to_string()}
                Pregunta: {pregunta}
                """
                
                with st.chat_message("assistant"):
                    try:
                        modelo = genai.GenerativeModel('gemini-1.5-flash')
                        respuesta = modelo.generate_content(contexto)
                        st.write(respuesta.text)
                    except Exception as e:
                        st.error(f"Hubo un error al consultar a Gemini: {e}")
        else:
            st.warning("Introduce tu API Key en la barra lateral para habilitar el análisis conversacional.")

else:
    # Pantalla inicial
    st.title("💼 Dashboard Recaall SpA")
    st.warning("Esperando carga de datos... Por favor, utiliza el panel lateral para subir el archivo CSV.")
    st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=1000", caption="Análisis Operativo", width=700)
