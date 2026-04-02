import pandas as pd
import logging
from mistralai import Mistral
from datetime import datetime
import os
import json
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
    logging.warning(f"📁 Excel: mtime={mtime}, size={size} bytes")

    # AÑADIR VALIDACIONES
    if not os.path.exists(ruta_excel):
        logging.error(f"❌ No existe {ruta_excel}")
        return (
            "❌ No encuentro tu archivo de inversiones.\n\n"
            "Comprueba que:\n"
            "• El volumen está montado\n"
            "• El archivo se llama 'bolsav2.xlsx'\n"
            "• Está en C:/Users/Robert/OneDrive/Documentos/"
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
        for _, fila in activas.iterrows():
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


def obtener_cartera_estructurada() -> dict:
    """
    Lee el Excel y devuelve datos reales estructurados de cada posición activa.

    Returns:
        {
          "hora_excel": str,
          "ultima_modificacion": str,
          "dolar": {"valor": float, "pct_dia": float},
          "oro":   {"valor": float, "pct_dia": float},
          "balance_total": float,
          "posiciones": [
              {
                "nombre": str,
                "valor_actual": float,   # precio actual (col J)
                "pct_dia": float,        # % cambio del día REAL (col Q × 100)
                "ganancia_total": float, # P&L acumulado en € (col O)
                "pct_total": float,      # % P&L acumulado (col P × 100)
                "take_profit": float,    # nivel TP (col R)
              }, ...
          ]
        }
    """
    ruta_excel = "/app/documentos/bolsav2.xlsx"
    if not os.path.exists(ruta_excel):
        return {}

    try:
        df = _leer_excel_snapshot(ruta_excel, hoja="Operaciones")
        ultima_mod = datetime.fromtimestamp(os.path.getmtime(ruta_excel)).strftime("%Y-%m-%d %H:%M:%S")

        def _safe(val, mult=1.0):
            try:
                return float(val) * mult if pd.notna(val) else 0.0
            except Exception:
                return 0.0

        hora_excel = str(df.iloc[0, 20]).split(".")[0] if pd.notna(df.iloc[0, 20]) else "N/D"
        dolar = {"valor": _safe(df.iloc[0, 23]), "pct_dia": _safe(df.iloc[0, 24], 100)}
        oro   = {"valor": _safe(df.iloc[1, 23]), "pct_dia": _safe(df.iloc[1, 24], 100)}

        activas = df[df.iloc[:, 8].isna()].copy()
        posiciones = []
        balance_total = 0.0

        for _, fila in activas.iterrows():
            nombre = str(fila.iloc[0]).strip()
            if not nombre or nombre.lower() in ("nan", "none", ""):
                continue
            gan = _safe(fila.iloc[14])
            balance_total += gan
            posiciones.append({
                "nombre":        nombre,
                "valor_actual":  _safe(fila.iloc[9]),
                "pct_dia":       _safe(fila.iloc[16], 100),  # col Q: % diario REAL
                "ganancia_total": gan,
                "pct_total":     _safe(fila.iloc[15], 100),
                "take_profit":   _safe(fila.iloc[17]),
            })

        return {
            "hora_excel": hora_excel,
            "ultima_modificacion": ultima_mod,
            "dolar": dolar,
            "oro": oro,
            "balance_total": balance_total,
            "posiciones": posiciones,
        }

    except Exception as e:
        logging.error(f"Error en obtener_cartera_estructurada: {e}")
        return {}


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




# ==================== NUEVAS FUNCIONALIDADES ====================

async def generar_resumen_semanal(client, config) -> str:
    """Genera un resumen del rendimiento semanal de la cartera + contexto de mercados."""
    import requests as req
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    fecha_hoy = datetime.now(ZoneInfo("Europe/Madrid"))
    lunes = fecha_hoy - timedelta(days=fecha_hoy.weekday())

    resumen_cartera = await asyncio.to_thread(analizar_inversiones)

    # Contexto semanal de mercados vía Tavily
    api_key = (config.get("tavily") or {}).get("api_key")
    contexto_mercados = "Sin datos de mercados disponibles."
    if api_key:
        try:
            r = await asyncio.to_thread(
                lambda: req.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": (
                            f"weekly stock market recap {fecha_hoy.strftime('%B %Y')} "
                            "Nasdaq IBEX performance this week key events"
                        ),
                        "search_depth": "advanced",
                        "max_results": 6,
                        "include_answer": True,
                    },
                    timeout=30,
                )
            )
            r.raise_for_status()
            data = r.json()
            bloques = []
            if data.get("answer"):
                bloques.append(data["answer"])
            for item in data.get("results", []):
                bloques.append(f"{item.get('title','')}: {item.get('content','')}")
            contexto_mercados = "\n\n".join(bloques[:5])
        except Exception as e:
            logging.warning(f"⚠️ Búsqueda semanal fallida: {e}")

    prompt = (
        f"Eres un analista financiero. Genera el resumen semanal del "
        f"{lunes.strftime('%d/%m')} al {fecha_hoy.strftime('%d/%m/%Y')}.\n\n"
        f"CARTERA ACTUAL:\n{resumen_cartera}\n\n"
        f"MERCADOS ESTA SEMANA:\n{contexto_mercados}\n\n"
        "ESTRUCTURA (Telegram móvil):\n\n"
        f"📊 RESUMEN SEMANAL — {lunes.strftime('%d/%m')} al {fecha_hoy.strftime('%d/%m/%Y')}\n\n"
        "TU CARTERA ESTA SEMANA\n"
        "• Mejor posición: nombre y rendimiento aprox.\n"
        "• Peor posición: nombre y rendimiento aprox.\n"
        "• Balance general de la semana.\n\n"
        "MERCADOS\n"
        "• Nasdaq esta semana: tendencia y % aprox.\n"
        "• IBEX esta semana: tendencia y % aprox.\n"
        "• Evento más relevante de la semana.\n\n"
        "PRÓXIMA SEMANA\n"
        "• 2-3 eventos o catalizadores a vigilar.\n"
        "• Una recomendación concreta y accionable.\n\n"
        "REGLAS: sin tablas, sin markdown complejo, viñetas cortas (máx 2 líneas), "
        "línea en blanco entre secciones, no inventar cifras exactas."
    )

    respuesta = await asyncio.to_thread(
        client.chat.complete,
        model="mistral-large-latest",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.15,
    )
    return respuesta.choices[0].message.content


async def noticias_valor_rapido(ticker: str, client, config) -> str:
    """Busca y sintetiza noticias recientes de un valor concreto."""
    import requests as req
    from datetime import datetime

    fecha = datetime.now().strftime("%B %Y")
    api_key = (config.get("tavily") or {}).get("api_key")

    if not api_key:
        return "❌ Tavily no configurado. Añade la api_key en config.yaml."

    try:
        r = await asyncio.to_thread(
            lambda: req.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": f"{ticker} noticias financieras esta semana resultados earnings {fecha}",
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": True,
                },
                timeout=20,
            )
        )
        r.raise_for_status()
        data = r.json()

        bloques = []
        if data.get("answer"):
            bloques.append(f"Resumen: {data['answer']}")
        for item in data.get("results", []):
            bloques.append(f"• {item.get('title','')}: {item.get('content','')[:300]}")
        contexto = "\n\n".join(bloques[:5]) or "Sin noticias recientes."

    except Exception as e:
        return f"❌ Error buscando noticias de {ticker}: {e}"

    prompt = (
        f"Sintetiza en 4-6 viñetas concisas las noticias más relevantes de {ticker.upper()} "
        f"para un inversor particular. Usa formato Telegram (sin markdown complejo).\n\n"
        f"INFORMACIÓN:\n{contexto}"
    )

    try:
        res = await asyncio.to_thread(
            client.chat.complete,
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return f"📰 Noticias {ticker.upper()}:\n\n{res.choices[0].message.content}"
    except Exception as e:
        return f"❌ Error sintetizando noticias: {e}"