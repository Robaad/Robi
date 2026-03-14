import pandas as pd
import logging
from mistralai import Mistral
from datetime import datetime
import os
import asyncio
import tempfile
import shutil

# Estos los importamos del main o de un config compartido luego
# Por ahora los definimos aquí para que el módulo sea funcional
MODELO_LISTO = "mistral-large-latest"


def _leer_excel_snapshot(ruta_excel: str, hoja: str = "Operaciones") -> pd.DataFrame:
    """
    Lee una copia temporal del Excel para evitar lecturas de caché/SO o archivo en escritura.

    OneDrive puede estar sincronizando el fichero mientras el bot lo lee.
    Copiamos primero a un archivo temporal y leemos esa instantánea estable.
    """
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        shutil.copy2(ruta_excel, tmp_path)
        return pd.read_excel(tmp_path, sheet_name=hoja)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def analizar_inversiones():
    ruta_excel = "/app/documentos/bolsav2.xlsx"
    
    mtime = os.path.getmtime(ruta_excel)
    size = os.path.getsize(ruta_excel)
    logging.info(f"📁 Excel: mtime={mtime}, size={size} bytes")

    # AÑADIR VALIDACIONES
    if not os.path.exists(ruta_excel):
        logging.error(f"❌ No existe {ruta_excel}")
        return (
            "❌ No encuentro tu archivo de inversiones.\n\n"
            "Comprueba que:\n"
            "• El volumen está montado en docker-compose.yml\n"
            "• El archivo se llama 'bolsav2.xlsx'\n"
            "• Está en la carpeta documentos del host"
        )

    try:
        # 1. LEER EL EXCEL (Fundamental hacerlo primero)
        df = _leer_excel_snapshot(ruta_excel, hoja='Operaciones')

        # Metadata para confirmar frescura del archivo
        ultima_modificacion = datetime.fromtimestamp(os.path.getmtime(ruta_excel)).strftime("%Y-%m-%d %H:%M:%S")
                     
        # --- BLOQUE ENCABEZADO (Dólar y Oro) ---
        try:
            hora_actual = df.iloc[0,20]
            hora_actual = str(hora_actual).split('.')[0]
            
            # DÓLAR (X2, Y2) -> Pandas Fila 0, Col 23, 24
            val_dolar = df.iloc[0, 23]
            pct_dolar = df.iloc[0, 24] * 100
            
            # ORO (X3, Y3) -> Pandas Fila 1, Col 23, 24
            val_oro = df.iloc[1, 23]
            pct_oro = df.iloc[1, 24] * 100
            
            # Limpieza de valores nulos o errores
            v_dol = float(val_dolar) if pd.notna(val_dolar) else 0.0
            p_dol = float(pct_dolar) if pd.notna(pct_dolar) else 0.0
            v_oro = float(val_oro) if pd.notna(val_oro) else 0.0
            p_oro = float(pct_oro) if pd.notna(pct_oro) else 0.0

            header = f"📅 **Hora cartera:** {hora_actual}\n"
            header += f"🕒 **Archivo actualizado:** {ultima_modificacion}\n"
            header += f"💵 **Dólar:** {v_dol:.4f}€ ({p_dol:+.2f}%)\n"
            header += f"🟡 **Oro:** {v_oro:,.2f}$/oz ({p_oro:+.2f}%)\n"
            header += "—" * 15 + "\n"
        except Exception as e:
            logging.error(f"Error en encabezado (Dólar/Oro): {e}")
            header = (
                f"💰 **Mercados:** Datos no disponibles temporalmente\n"
                f"🕒 **Archivo actualizado:** {ultima_modificacion}\n\n"
            )

        # --- FILTRAR ACTIVAS (Columna I vacía) ---
        # La columna I es el índice 8
        activas = df[df.iloc[:, 8].isna()].copy()
        
        if activas.empty:
            return header + "No hay inversiones activas."
        
        reporte = header + "📈 **Tus inversiones activas:**\n\n"
        
        # Variable para el sumatorio total
        total_ganancia_acumulada = 0.0

        # --- BLOQUE DE INVERSIONES ---
        for i in range(len(activas)):
            fila = activas.iloc[i]
            
            nombre = fila.iloc[0]          # Columna A
            valor_dia = fila.iloc[9]       # Columna J
            pct_dia = fila.iloc[16] * 100  # Columna Q
            ganancia_tot = fila.iloc[14]   # Columna O
            pct_tot = fila.iloc[15] * 100  # Columna P
            take_profit = fila.iloc[17]    # Columna R
            
            # Sumar al total (manejando posibles nulos)
            if pd.notna(ganancia_tot):
                total_ganancia_acumulada += float(ganancia_tot)

            # Formateo de iconos
            icono = "🟢" if ganancia_tot >= 0 else "🔴"
            tendencia = "🔼" if pct_dia >= 0 else "🔻"
            
            reporte += f"{icono} **{nombre}**\n"
            reporte += f"   Hoy: {valor_dia:.2f}€ {tendencia} ({pct_dia:+.2f}%)\n"
            reporte += f"   Total: {ganancia_tot:.2f}€ ({pct_tot:+.2f}%)\n"
            reporte += f"   Take Profit: {take_profit:.2f}€"
            reporte += "🟢" if (valor_dia-take_profit) >= 0 else "🔴"
            reporte += "\n\n"
        
        # --- BLOQUE CIERRE (Sumatorio Total) ---
        icono_total = "✅" if total_ganancia_acumulada >= 0 else "🚨"
        color_texto = "🟢" if total_ganancia_acumulada >= 0 else "🔴"
        
        reporte += "—" * 15 + "\n"
        reporte += f"{icono_total} **BALANCE TOTAL: {color_texto} {total_ganancia_acumulada:,.2f}€**"

        return reporte
        
    except Exception as e:
        logging.error(f"Error al leer el Excel: {e}")
        return f"❌ Error: {str(e)}"


def obtener_lista_seguimiento():
    """Lee la lista de seguimiento desde columnas V (nombre), X (valor), Y (% diario)."""
    ruta_excel = "/app/documentos/bolsav2.xlsx"

    if not os.path.exists(ruta_excel):
        logging.error(f"❌ No existe {ruta_excel}")
        return "❌ No encuentro tu archivo de inversiones para leer el seguimiento."

    try:
        df = _leer_excel_snapshot(ruta_excel, hoja="Operaciones")
        ultima_modificacion = datetime.fromtimestamp(os.path.getmtime(ruta_excel)).strftime("%Y-%m-%d %H:%M:%S")

        # Columnas Excel: V=21, X=23, Y=24 (index 0-based)
        seguimiento = df.iloc[:, [21, 23, 24, 25]].copy()
        seguimiento.columns = ["nombre", "valor_actual", "pct_diario", "entrada"]
        seguimiento = seguimiento[seguimiento["nombre"].notna()]

        if seguimiento.empty:
            return (
                "👀 **Seguimiento**\n"
                f"🕒 Archivo actualizado: {ultima_modificacion}\n\n"
                "No hay valores en la columna V."
            )

        reporte = (
            "👀 **Seguimiento**\n"
            f"🕒 Archivo actualizado: {ultima_modificacion}\n"
            "━━━━━━━━━━━━━━\n"
        )

        for _, fila in seguimiento.iterrows():
            nombre = str(fila["nombre"]).strip()
            valor_actual = float(fila["valor_actual"]) if pd.notna(fila["valor_actual"]) else 0.0
            pct_diario = float(fila["pct_diario"]) * 100 if pd.notna(fila["pct_diario"]) else 0.0
            entrada = float(fila["entrada"]) if pd.notna(fila["entrada"]) else 0.0
            icono = "🟢" if pct_diario >= 0 else "🔴"
            icono_entrada = "🟢" if entrada >= valor_actual else "🔴"

            reporte += f"{icono} **{nombre}**\n"
            reporte += f"   Valor actual: {valor_actual:,.2f}\n"
            reporte += f"   % diario: {pct_diario:+.2f}%\n"
            if (entrada > 0.0):
                reporte += f"   % Entrada: {entrada:,.2f} {icono_entrada}"
            reporte += "\n\n"

        return reporte
    except Exception as e:
        logging.error(f"Error al leer seguimiento en el Excel: {e}")
        return f"❌ Error leyendo seguimiento: {str(e)}"


# =============================================================================
# NUEVA FUNCIÓN: buscar_oportunidades_inversion con evaluador profesional
# =============================================================================

async def buscar_oportunidades_inversion(mercado: str, client, buscar_internet, evaluador=None):
    """
    Busca acciones con alto potencial de crecimiento en Nasdaq o Ibex.
    
    Nueva versión: Usa el evaluador profesional para análisis profundo de cada candidato.
    
    Args:
        mercado: "nasdaq" o "ibex"
        client: Cliente de Mistral
        buscar_internet: Función para buscar en internet
        evaluador: Instancia de EvaluadorProfesionalCartera (opcional)
    
    Returns:
        str: Informe formateado con las oportunidades encontradas
    """
    try:
        logging.info(f"🔍 Escaneando {mercado.upper()} con análisis profesional...")
        
        # FASE 1: Búsqueda inicial de candidatos
        if "nasdaq" in mercado.lower():
            query = "best growth stocks nasdaq 2026 high upside analyst ratings top picks"
        else:
            query = "mejores acciones ibex 35 con potencial crecimiento 2026 dividendos consenso analistas"

        contexto = await asyncio.to_thread(buscar_internet, query)

        # FASE 2: Extraer candidatos con Mistral
        prompt_candidatos = f"""
        Basándote en esta información:
        {contexto}
        
        TAREA:
        Identifica EXACTAMENTE 3 tickers/empresas con mayor potencial en {mercado.upper()}.
        
        Responde SOLO con formato JSON:
        {{
            "candidatos": [
                {{"ticker": "AAPL", "nombre": "Apple Inc"}},
                {{"ticker": "MSFT", "nombre": "Microsoft Corp"}},
                {{"ticker": "NVDA", "nombre": "NVIDIA Corp"}}
            ]
        }}
        
        REGLAS:
        - Solo tickers reales y actuales
        - Solo 3 candidatos
        - Sin explicaciones adicionales
        """

        res = await asyncio.to_thread(
            client.chat.complete,
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt_candidatos}],
            temperature=0.2
        )
        
        # Parsear respuesta
        import json
        try:
            respuesta_json = res.choices[0].message.content
            # Limpiar posibles markdown
            respuesta_json = respuesta_json.replace('```json', '').replace('```', '').strip()
            candidatos_data = json.loads(respuesta_json)
            candidatos = candidatos_data.get('candidatos', [])
        except Exception as e:
            logging.error(f"Error parseando candidatos: {e}")
            return f"❌ No pude identificar candidatos válidos en {mercado}"

        if not candidatos or len(candidatos) == 0:
            return f"❌ No se encontraron candidatos válidos en {mercado}"

        # FASE 3: Evaluar cada candidato con el evaluador profesional
        if evaluador is None:
            return _formato_simple_oportunidades(candidatos, mercado)
        
        evaluaciones = []
        for candidato in candidatos[:3]:  # Max 3
            ticker = candidato.get('ticker', '')
            nombre = candidato.get('nombre', ticker)
            
            logging.info(f"  📊 Evaluando {ticker}...")
            
            try:
                evaluacion = await evaluador.evaluar_valor_unico(f"{ticker} {nombre}")
                if evaluacion.get('success'):
                    evaluaciones.append(evaluacion['evaluaciones'][0])
                else:
                    logging.warning(f"  ⚠️ No se pudo evaluar {ticker}")
            except Exception as e:
                logging.error(f"  ❌ Error evaluando {ticker}: {e}")
                continue

        # FASE 4: Formatear resultados
        if not evaluaciones:
            return _formato_simple_oportunidades(candidatos, mercado)
        
        return _formatear_oportunidades_profesional(evaluaciones, mercado)

    except Exception as e:
        logging.error(f"Error en escáner de oportunidades: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ No pude escanear el mercado {mercado} en este momento."


def _formato_simple_oportunidades(candidatos, mercado):
    """Formato simple cuando no hay evaluador disponible."""
    msg = f"🔍 **OPORTUNIDADES EN {mercado.upper()}**\n\n"
    msg += "Candidatos identificados (requieren análisis adicional):\n\n"
    for i, c in enumerate(candidatos[:3], 1):
        msg += f"{i}. **{c.get('ticker')}** - {c.get('nombre')}\n"
    msg += "\n💡 Usa /deep [TICKER] para análisis detallado de cada candidato."
    return msg


def _formatear_oportunidades_profesional(evaluaciones, mercado):
    """Formatea resultados con análisis profesional."""
    from evaluador_profesional import formatear_evaluacion_individual_profesional
    
    msg = f"🎯 **OPORTUNIDADES DE INVERSIÓN - {mercado.upper()}**\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"**Análisis Profesional de Top 3 Candidatos**\n"
    msg += f"Metodología: Análisis Multi-Capa (Técnico + Fundamental + Consenso)\n\n"
    
    # Ordenar por upside potencial (mayor primero)
    evaluaciones_ordenadas = sorted(
        evaluaciones,
        key=lambda x: float(x['recomendacion'].get('upside_potencial', 0)),
        reverse=True
    )
    
    for i, ev in enumerate(evaluaciones_ordenadas, 1):
        msg += f"**#{i} OPORTUNIDAD**\n"
        msg += formatear_evaluacion_individual_profesional(ev)
        msg += "\n"
    
    # Resumen comparativo
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "**COMPARATIVA RÁPIDA:**\n\n"
    
    for ev in evaluaciones_ordenadas:
        nombre = ev.get('nombre', 'N/A')
        accion = ev['recomendacion'].get('accion', 'N/A')
        upside = ev['recomendacion'].get('upside_potencial', 0)
        riesgo = ev['recomendacion'].get('riesgo', 'N/A')
        
        icono = '🟢' if accion in ['COMPRAR', 'AUMENTAR'] else '🟡' if accion == 'MANTENER' else '🔴'
        
        msg += f"{icono} **{nombre}**: {accion} | Upside: {upside:+.1f}% | Riesgo: {riesgo}\n"
    
    msg += "\n⚠️ Estos análisis son orientativos. Valida antes de invertir.\n"
    
    return msg


#--ASESON FINANCIERO--
def super_asesor_financiero(nombre_valor: str, client, buscar_internet):
    try:
        df = _leer_excel_snapshot("/app/documentos/bolsav2.xlsx", hoja='Operaciones')
        
        # Si Mistral mandó 'acciones', intentamos ayudarle
        if nombre_valor.lower() in ["acciones", "cartera", "mis valores"]:
            valores_en_cartera = df[df.iloc[:, 8].isna()].iloc[:, 0].tolist()
            return f"¿Sobre qué valor de tu cartera quieres que me moje? Tienes: {', '.join(valores_en_cartera)}"

        # Filtrar por el nombre real
        cartera = df[df.iloc[:, 0].str.contains(nombre_valor, case=False, na=False) & df.iloc[:, 8].isna()]
        
        if not cartera.empty:
            # Cogemos datos reales del Excel
            p_compra = cartera.iloc[0, 5]   # Columna F
            beneficio = cartera.iloc[0, 14]  # Columna O
            pct = cartera.iloc[0, 15] * 100  # Columna P
            info_cartera = f"Tienes {nombre_valor} compradas a {p_compra:.2f}€. Vas ganando {beneficio:.2f}€ ({pct:+.2f}%)."
        else:
            info_cartera = f"No tienes {nombre_valor} en tu Excel actualmente."

        # Búsqueda externa
        query = f"consensus target price analyst {nombre_valor} 2026"
        info_mercado = buscar_internet(query)

        prompt_final = f"""
            Eres un asesor senior. 
            CONTEXTO: {info_cartera}
            MERCADO: {info_mercado}
            
            TAREA:
            Dame una orden clara: COMPRAR, MANTENER o VENDER.
            Justifica brevemente.
            
            ⚠️ REGLA CRÍTICA: Tu respuesta total NO puede superar los 2000 caracteres. 
            Sé muy conciso y ve al grano.
            """


        res = client.chat.complete(model=MODELO_LISTO, messages=[{"role": "user", "content": prompt_final}])
        return res.choices[0].message.content

    except Exception as e:
        return f"❌ Error al acceder a los datos: {e}"

def recomendar_valor(nombre_valor: str, client, buscar_internet):
    """Robi busca el precio objetivo y da una recomendación basada en analistas."""
    try:
        query = f"target price consensus analyst {nombre_valor} 2026"
        info_mercado = buscar_internet(query) 
        
        prompt = f"""
        Eres un analista financiero experto. Basándote en esta información: "{info_mercado}"
        Para el valor {nombre_valor}, resume:
        1. Precio objetivo medio (Target Price).
        2. Recomendación general (Comprar, Mantener, Vender).
        3. Un motivo breve.
        """
        
        respuesta = client.chat.complete(
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return respuesta.choices[0].message.content
    except Exception as e:
        return f"Robi: No he podido calcular el valor objetivo ahora mismo. {str(e)}"

def buscar_noticias_valor(nombre_valor: str, client, buscar_internet):
    """Busca noticias financieras recientes para explicar movimientos de precio."""
    query = f"últimas noticias financieras por qué sube o baja {nombre_valor} hoy 2026"
    
    contexto_noticias = buscar_internet(query)
    
    prompt = f"""
    Basándote en estas noticias: "{contexto_noticias}"
    Explica de forma breve y clara por qué {nombre_valor} se está moviendo hoy.
    Si hay algún evento importante, menciónalo.
    """
    
    response = client.chat.complete(
        model=MODELO_LISTO,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content