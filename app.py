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
    st.image("https://images.unsplash.com/photo-1596524430615-b46475ddff6e?auto=format&fit=crop&q=80&w=300", width=150) # Imagen elegante relacionada a contacto
    st.header("📂 Panel de Datos")
    archivo_subido = st.file_uploader("Cargar reporte BCI (.csv)", type=["csv"])
    st.info("Sube el archivo CSV extraído de la plataforma para analizar los resultados.")
    
    st.divider()
    st.header("🤖 Inteligencia Gemini")
    api_key = st.text_input("Ingresa tu Gemini API Key", type="password", help="Obtén tu clave en Google AI Studio.")
    if api_key:
        genai.configure(api_key=api_key)

# --- CUERPO PRINCIPAL ---
if archivo_subido:
    df = procesar_datos(archivo_subido)
    
    if df is not None:
        st.title("📊 Resumen de Conversión Operativa")
        
        # Filtros Superiores Dinámicos
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            campanas_unicas = df['GES_nombre_campana_gestion'].unique()
            campanas = st.multiselect("Campaña(s)", campanas_unicas, default=campanas_unicas[0] if len(campanas_unicas)>0 else None)
        with c_f2:
            ejecutivos = st.multiselect("Ejecutivo(s)", df['GES_username_recurso'].unique())
        with c_f3:
            # Lógica de filtrado
            df_final = df[df['GES_nombre_campana_gestion'].isin(campanas)]
            if ejecutivos:
                df_final = df_final[df_final['GES_username_recurso'].isin(ejecutivos)]
            
            # Exportación a Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Reporte_Filtrado')
            
            # Espaciado para alinear botón
            st.write("##") 
            st.download_button(
                label="📥 Descargar Selección a Excel",
                data=output.getvalue(),
                file_name=f"reporte_recaall_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("---")

        # --- SECCIÓN DE MÉTRICAS (ELEGANTES Y SOBRIAS) ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Llamados Totales", len(df_final))
        m2.metric("Ventas (Confirmadas)", df_final['es_venta'].sum())
        
        t_conv = (df_final['es_venta'].sum()/len(df_final)*100 if len(df_final)>0 else 0)
        m3.metric("% Tasa de Conversión", f"{t_conv:.2f}%")
        m4.metric("Días Operativos", df_final['Día'].nunique())

        st.markdown("---")

        # --- GRÁFICO DIARIO DE TENDENCIA (LÍNEAS) ---
        st.subheader("📅 Evolución Diaria de Resultados")
        tendencia_diaria = df_final.groupby('Día').agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
        tendencia_diaria['Día'] = tendencia_diaria['Día'].astype(str) # Para Plotly eje X

        fig_linea = px.line(tendencia_diaria, x='Día', y=['Llamados', 'Ventas'], 
                            markers=True, template="plotly_dark",
                            color_discrete_map={'Llamados': color_effort, 'Ventas': color_success})
        
        fig_linea.update_layout(
            hovermode="x unified",
            paper_bgcolor=color_bg_main,
            plot_bgcolor=color_bg_main,
            margin=dict(l=0, r=0, t=20, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
        )
        st.plotly_chart(fig_linea, use_container_width=True)


        # --- OTROS GRÁFICOS DINÁMICOS ---
        st.markdown("### 📊 Concentración Operativa")
        col_g1, col_g2 = st.columns([2, 1])

        with col_g1:
            st.markdown("#### Distribución de Ventas por Franja")
            agrupacion_temporal = st.radio("Agrupar concentración por:", ["Hora", "Semana"], horizontal=True)
            
            resumen_temp = df_final.groupby(agrupacion_temporal).agg(Llamados=('es_venta', 'count'), Ventas=('es_venta', 'sum')).reset_index()
            resumen_temp[agrupacion_temporal] = resumen_temp[agrupacion_temporal].astype(str) 
            
            fig_bar = px.bar(resumen_temp, x=agrupacion_temporal, y=['Llamados', 'Ventas'], 
                             barmode='group', template="plotly_dark",
                             color_discrete_map={'Llamados': color_effort, 'Ventas': color_success})
            
            fig_bar.update_layout(
                paper_bgcolor=color_bg_main, plot_bgcolor=color_bg_main,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_g2:
            st.markdown("#### Principales Motivos No Venta")
            motivos = df_final[df_final['es_venta'] == 0]['GES_descripcion_2'].value_counts().head(6)
            
            # Usamos un mapa de colores sobrio y profesional para la torta
            colores_pie = px.colors.sequential.Agsunset_r

            fig_pie = px.pie(values=motivos.values, names=motivos.index, hole=.6, template="plotly_dark",
                             color_discrete_sequence=colores_pie)
            
            fig_pie.update_layout(
                paper_bgcolor=color_bg_main, plot_bgcolor=color_bg_main,
                showlegend=False, 
                margin=dict(t=0, b=0, l=0, r=0)
            )
            # Agregamos texto en el centro para el look profesional
            fig_pie.add_annotation(text="Top Fugas", x=0.5, y=0.5, showarrow=False, font_size=18, font_color=color_text)
            
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- ANÁLISIS Y CONCLUSIONES AUTOMÁTICAS (STILIZADAS) ---
        st.markdown("---")
        st.subheader("📝 Análisis Diagnóstico por Campaña")
        for camp in campanas:
            df_camp = df_final[df_final['GES_nombre_campana_gestion'] == camp]
            if not df_camp.empty:
                t_llamados = len(df_camp)
                t_ventas = df_camp['es_venta'].sum()
                t_conv = (t_ventas / t_llamados * 100) if t_llamados > 0 else 0
                mejor_ejecutivo = df_camp.groupby('GES_username_recurso')['es_venta'].sum().idxmax() if t_ventas > 0 else "Sin Ventas"
                
                # Estas cajas st.info ahora se ven elegantes con el CSS aplicado
                st.info(f"""
                **{camp}:** Se registraron **{t_llamados:,}** gestiones y **{t_ventas:,}** ventas efectivas, logrando una tasa de conversión de **{t_conv:.2f}%**. 
                El ejecutivo destacado en volumen de cierre es **{mejor_ejecutivo}**.
                """)

        # Tabla detallada por ejecutivo (Con dataframe elegante)
        st.subheader("Detalle General por Ejecutivo (Top 10 Cierres)")
        ranking = df_final.groupby('GES_username_recurso').agg(
            Llamados=('es_venta', 'count'),
            Ventas=('es_venta', 'sum')
        ).reset_index()
        
        ranking['% Conversión'] = (ranking['Ventas'] / ranking['Llamados'] * 100).round(2)
        ranking = ranking.sort_values(by='Ventas', ascending=False)
        
        st.dataframe(ranking.head(10), use_container_width=True, hide_index=True)

        # Apartado IA
        st.markdown("---")
        st.subheader("🤖 Consultoría Analítica Gemini")
        st.caption("Pregunta sobre los indicadores actuales, días clave o rendimiento de ejecutivos.")
        
        if api_key:
            pregunta = st.chat_input("Escribe tu consulta analítica aquí...")
            if pregunta:
                with st.chat_message("user"):
                    st.write(pregunta)
                
                # Contexto optimizado para IA
                contexto = f"""
                Responde de forma ejecutiva y profesional como analista de datos Senior. 
                Los siguientes datos resumen la operación actual filtrada en pantalla:
                
                RESUMEN DIARIO:\n{tendencia_diaria.to_string()}\n
                RENDIMIENTO TOP EJECUTIVOS (Ventas):\n{ranking.head(10).to_string()}\n
                
                Instrucción: Basándote EXCLUSIVAMENTE en estos datos, responde a la pregunta del usuario. 
                Si la respuesta no está en los datos, dilo amablemente.
                
                Pregunta del Usuario: {pregunta}
                """
                
                with st.chat_message("assistant"):
                    try:
                        modelo = genai.GenerativeModel('gemini-1.5-flash')
                        respuesta = modelo.generate_content(contexto)
                        st.write(respuesta.text)
                    except Exception as e:
                        st.error(f"Hubo un error al conectar con Gemini: {e}")
        else:
            st.warning("⚠️ Ingresa tu API Key en la barra lateral para activar el análisis conversacional de Gemini.")

else:
    # Pantalla inicial
    st.title("💼 Dashboard Operativo Recaall")
    st.divider()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info("👋 Bienvenido a tu Panel Analítico.\n\nPor favor, utiliza el panel lateral para subir el archivo CSV de gestión comercial extraído de BCI.")
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=1000", caption="Análisis Operativo Inteligente", width=700)
