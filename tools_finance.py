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
# ESCÁNER DE OPORTUNIDADES — versión 2
# =============================================================================

async def buscar_oportunidades_inversion(mercado: str, client, buscar_internet, evaluador=None):
    try:
        logging.info("🔍 Iniciando escáner de oportunidades en %s...", mercado.upper())
        es_nasdaq = "nasdaq" in mercado.lower()

        if es_nasdaq:
            queries_candidatos = [
                f"nasdaq stocks analyst upgrade strong buy price target increase {datetime.now().strftime('%B %Y')}",
                f"nasdaq undervalued stocks low PEG high growth earnings beat {datetime.now().strftime('%Y')}",
                f"nasdaq momentum breakout stocks high volume surge {datetime.now().strftime('%B %Y')}",
            ]
        else:
            queries_candidatos = [
                f"IBEX 35 acciones recomendacion compra mejora rating analistas {datetime.now().strftime('%B %Y')}",
                f"IBEX 35 acciones infravaloradas PER bajo dividendo alto potencial {datetime.now().strftime('%Y')}",
                f"bolsa española acciones momentum subida volumen maximos {datetime.now().strftime('%B %Y')}",
            ]

        contextos = []
        for q in queries_candidatos:
            try:
                resultado = await asyncio.to_thread(buscar_internet, q)
                contextos.append(resultado)
            except Exception as e:
                logging.warning("Busqueda candidatos fallida: %s", e)
                contextos.append("")

        contexto_combinado = "\n\n---\n\n".join(
            f"[Busqueda {i+1}]\n{c[:800]}" for i, c in enumerate(contextos) if c
        )

        prompt_candidatos = (
            f"Eres un analista bursatil. Analiza estas busquedas y extrae los valores "
            f"con mayor potencial en {mercado.upper()} a 6-12 meses.\n\n"
            f"INFORMACION DE MERCADO:\n{contexto_combinado}\n\n"
            "TAREA: Identifica EXACTAMENTE 3 tickers distintos con mayor potencial. "
            "Prioriza: upgrades de analistas, momentum positivo, valoracion atractiva. "
            "Evita mega-caps evidentes (AAPL, MSFT, NVDA, AMZN, GOOGL) "
            "salvo que tengan catalizador muy especifico.\n\n"
            "Responde SOLO JSON:\n"
            "{\n"
            '  "candidatos": [\n'
            '    {"ticker": "TICKER1", "nombre": "Nombre", "razon_seleccion": "Por que es oportunidad"},\n'
            '    {"ticker": "TICKER2", "nombre": "Nombre", "razon_seleccion": "..."},\n'
            '    {"ticker": "TICKER3", "nombre": "Nombre", "razon_seleccion": "..."}\n'
            "  ]\n"
            "}"
        )

        from tools_system import mistral_chat_with_retry
        res = await mistral_chat_with_retry(
            client,
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt_candidatos}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        try:
            candidatos_data = json.loads(res.choices[0].message.content)
            candidatos = candidatos_data.get("candidatos", [])[:3]
        except Exception as e:
            logging.error("Error parseando candidatos: %s", e)
            return "❌ No pude identificar candidatos en " + mercado

        if not candidatos:
            return "❌ Sin candidatos validos en " + mercado

        logging.info("Candidatos: %s", [c.get("ticker") for c in candidatos])

        analisis_candidatos = []
        for candidato in candidatos:
            ticker = candidato.get("ticker", "")
            nombre = candidato.get("nombre", ticker)
            razon  = candidato.get("razon_seleccion", "")
            analisis = await _analizar_candidato_rapido(ticker, nombre, razon, client, buscar_internet)
            analisis_candidatos.append(analisis)

        return _formatear_oportunidades_v2(analisis_candidatos, mercado)

    except Exception as e:
        logging.error("Error en escaner de oportunidades: %s", e)
        import traceback; traceback.print_exc()
        return "❌ No pude escanear " + mercado + " en este momento."


async def _analizar_candidato_rapido(ticker, nombre, razon_seleccion, client, buscar_internet):
    from tools_system import mistral_chat_with_retry
    fecha = datetime.now().strftime("%B %Y")

    query = (
        ticker + " " + nombre + " analyst target price consensus recommendation "
        "earnings revenue growth PE ratio " + fecha
    )
    try:
        contexto = await asyncio.to_thread(buscar_internet, query)
    except Exception as e:
        logging.warning("Busqueda rapida fallida para %s: %s", ticker, e)
        contexto = ""

    prompt = (
        "Eres un analista de renta variable. Analiza este valor.\n\n"
        "VALOR: " + ticker + " — " + nombre + "\n"
        "RAZON DE SELECCION: " + razon_seleccion + "\n"
        "FECHA: " + fecha + "\n\n"
        "INFORMACION DE MERCADO:\n" + contexto[:2500] + "\n\n"
        "Responde UNICAMENTE en JSON con esta estructura exacta:\n"
        "{\n"
        '  "precio_actual_usd": numero_o_null,\n'
        '  "precio_objetivo_consenso": numero_o_null,\n'
        '  "upside_consenso_pct": numero_o_null,\n'
        '  "recomendacion_consenso": "Strong Buy|Buy|Hold|Sell|Strong Sell|null",\n'
        '  "num_analistas": numero_o_null,\n'
        '  "per": numero_o_null,\n'
        '  "crecimiento_ingresos_pct": numero_o_null,\n'
        '  "margen_operativo_pct": numero_o_null,\n'
        '  "catalizadores": ["catalizador 1", "catalizador 2"],\n'
        '  "riesgos": ["riesgo 1", "riesgo 2"],\n'
        '  "horizonte_recomendado": "corto|medio|largo",\n'
        '  "conviction_score": numero_entre_0_y_10,\n'
        '  "resumen_tesis": "Tesis en 2 frases maximo",\n'
        '  "calidad_datos": "alta|media|baja"\n'
        "}\n\n"
        "conviction_score: 0-3=evitar, 4-6=vigilar, 7-10=oportunidad clara.\n"
        "calidad_datos: alta si tienes precio objetivo+PER+consenso; baja si faltan 2 o mas.\n"
        "Si un dato no esta disponible usa null, no inventes."
    )

    try:
        res = await mistral_chat_with_retry(
            client,
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        datos = json.loads(res.choices[0].message.content)
    except Exception as e:
        logging.error("Error analizando %s: %s", ticker, e)
        datos = {"calidad_datos": "baja", "conviction_score": 0}

    datos["ticker"] = ticker
    datos["nombre"] = nombre
    datos["razon_seleccion"] = razon_seleccion
    return datos


def _formato_simple_oportunidades(candidatos, mercado):
    msg = "🔍 OPORTUNIDADES EN " + mercado.upper() + "\n\n"
    for i, c in enumerate(candidatos[:3], 1):
        msg += str(i) + ". " + c.get("ticker", "") + " - " + c.get("nombre", "") + "\n"
    msg += "\n💡 Usa /deep TICKER para analisis detallado."
    return msg


def _formatear_oportunidades_v2(candidatos, mercado):
    fecha = datetime.now().strftime("%d/%m/%Y")

    candidatos_ordenados = sorted(
        candidatos,
        key=lambda x: x.get("conviction_score", 0),
        reverse=True,
    )

    def icono_conv(score):
        s = int(score or 0)
        if s >= 7: return "🟢"
        if s >= 4: return "🟡"
        return "🔴"

    iconos_rec = {
        "Strong Buy": "🟢🟢", "Buy": "🟢", "Hold": "🟡",
        "Sell": "🔴", "Strong Sell": "🔴🔴",
    }

    lineas = [
        "🎯 ESCANER DE OPORTUNIDADES — " + mercado.upper(),
        "📅 " + fecha + " · Analisis multi-fuente",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, c in enumerate(candidatos_ordenados, 1):
        ticker    = c.get("ticker", "N/A")
        nombre    = c.get("nombre", ticker)
        score     = c.get("conviction_score", 0)
        calidad   = c.get("calidad_datos", "baja")
        razon     = c.get("razon_seleccion", "")
        tesis     = c.get("resumen_tesis") or ""
        rec       = c.get("recomendacion_consenso") or "N/D"
        upside    = c.get("upside_consenso_pct")
        precio    = c.get("precio_actual_usd")
        objetivo  = c.get("precio_objetivo_consenso")
        per       = c.get("per")
        crec      = c.get("crecimiento_ingresos_pct")
        analistas = c.get("num_analistas")
        cats      = c.get("catalizadores", [])
        riesgos   = c.get("riesgos", [])
        horizonte = c.get("horizonte_recomendado", "medio")
        ico = icono_conv(score)

        lineas.append("#" + str(i) + " " + ico + " " + ticker + " — " + nombre)
        lineas.append("Conviccion: " + str(score) + "/10  |  Datos: " + calidad + "  |  Horizonte: " + horizonte)
        if razon:
            lineas.append("• Por que: " + razon)

        quant = []
        if precio: quant.append("Precio: " + f"{precio:.2f}$")
        if objetivo: quant.append("Objetivo: " + f"{objetivo:.2f}$")
        if upside is not None: quant.append("Upside: " + f"{upside:+.1f}%")
        if per: quant.append("PER: " + f"{per:.1f}x")
        if crec is not None: quant.append("Crec.ingresos: " + f"{crec:+.1f}%")
        if analistas: quant.append("Analistas: " + str(analistas))
        if quant:
            lineas.append("• " + "  |  ".join(quant))

        if rec and rec != "N/D":
            ico_r = iconos_rec.get(rec, "")
            lineas.append("• Consenso: " + ico_r + " " + rec)
        if tesis:
            lineas.append("• Tesis: " + tesis)
        if cats:
            lineas.append("• ✅ " + " / ".join(cats[:2]))
        if riesgos:
            lineas.append("• ⚠️ " + " / ".join(riesgos[:2]))
        lineas.append("")

    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lineas.append("RANKING:")
    for c in candidatos_ordenados:
        ticker = c.get("ticker", "N/A")
        score  = c.get("conviction_score", 0)
        upside = c.get("upside_consenso_pct")
        rec    = c.get("recomendacion_consenso") or "N/D"
        ico    = icono_conv(score)
        up_str = (f"{upside:+.1f}%") if upside is not None else "N/D"
        lineas.append(ico + " " + ticker + ": " + str(score) + "/10 · " + rec + " · Upside " + up_str)

    lineas.append("")
    lineas.append("💡 Para analisis tecnico completo: /deep TICKER")
    lineas.append("⚠️ Analisis orientativo. Valida antes de operar.")

    return "\n".join(lineas)




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