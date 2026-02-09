import pandas as pd
import logging
from mistralai import Mistral
from datetime import datetime
import os
import asyncio

# Estos los importamos del main o de un config compartido luego
# Por ahora los definimos aquí para que el módulo sea funcional
MODELO_LISTO = "mistral-large-latest"

def analizar_inversiones():
    ruta_excel = "/app/documentos/bolsav2.xlsx"
    
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
        df = pd.read_excel(ruta_excel, sheet_name='Operaciones')
                     
        # --- BLOQUE ENCABEZADO (Dólar y Oro) ---
        try:
            hora_actual = df.iloc[0,17]
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

            header = f"📅 **Hora:** {hora_actual}\n"
            header += f"💵 **Dólar:** {v_dol:.4f}€ ({p_dol:+.2f}%)\n"
            header += f"🟡 **Oro:** {v_oro:,.2f}$/oz ({p_oro:+.2f}%)\n"
            header += "—" * 15 + "\n"
        except Exception as e:
            logging.error(f"Error en encabezado (Dólar/Oro): {e}")
            header = "💰 **Mercados:** Datos no disponibles temporalmente\n\n"

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
            
            # Sumar al total (manejando posibles nulos)
            if pd.notna(ganancia_tot):
                total_ganancia_acumulada += float(ganancia_tot)

            # Formateo de iconos
            icono = "🟢" if ganancia_tot >= 0 else "🔴"
            tendencia = "🔼" if pct_dia >= 0 else "🔻"
            
            reporte += f"{icono} **{nombre}**\n"
            reporte += f"   Hoy: {valor_dia:.2f}€ {tendencia} ({pct_dia:+.2f}%)\n"
            reporte += f"   Total: {ganancia_tot:.2f}€ ({pct_tot:+.2f}%)\n\n"
        
        # --- BLOQUE CIERRE (Sumatorio Total) ---
        icono_total = "✅" if total_ganancia_acumulada >= 0 else "🚨"
        color_texto = "🟢" if total_ganancia_acumulada >= 0 else "🔴"
        
        reporte += "—" * 15 + "\n"
        reporte += f"{icono_total} **BALANCE TOTAL: {color_texto} {total_ganancia_acumulada:,.2f}€**"

        return reporte
        
    except Exception as e:
        logging.error(f"Error al leer el Excel: {e}")
        return f"❌ Error: {str(e)}"

#--- deep rresearch
async def realizar_deep_research(nombre_valor: str, client, buscar_internet):
    """Investigación multietapa: Técnica, Fundamental y Sentimiento."""
    try:
        logging.info(f"🚀 Iniciando Deep Research para: {nombre_valor}")
                
        # --- OBTENER FECHA ACTUAL ---
        hoy = datetime.now()
        fecha_str = hoy.strftime("%d de %B de %Y") # Ejemplo: 07 de February de 2026

        # FASE 1: Búsqueda diversificada
        queries = [
            f"precio accion {nombre_valor} tiempo real hoy {fecha_str}",
            f"análisis fundamental {nombre_valor} 2026 resultados ingresos deuda",
            f"precio objetivo consenso analistas bancos {nombre_valor} febrero 2026",
            f"riesgos geopolíticos y de mercado para {nombre_valor} hoy",
            f"análisis técnico niveles soporte y resistencia {nombre_valor}"
        ]
        
        contexto_acumulado = ""
        for q in queries:
            res = await asyncio.to_thread(buscar_internet, q)
            contexto_acumulado += f"\n--- INFO DE: {q} ---\n{res}\n"

        # FASE 2: Super Prompt de Análisis
        prompt_pro = f"""
        Actúa como un Analista Senior de Equity Research. 
        VALOR A ANALIZAR: {nombre_valor}
        FECHA DEL INFORME: {fecha_str}
        REGLA OBLIGATORIA: DEBES obtener primero el precio real de HOY usando BUSCAR, ejemplo: 'precio accion META hoy' antes de generar el comando DEEP_RESEARCH."
        
        DATOS RECOPILADOS:
        {contexto_acumulado}
        
        ESTRUCTURA DEL INFORME:
        1. 📊 **TESIS DE INVERSIÓN**: Resumen ejecutivo de la situación actual.
        2. 📈 **FUNDAMENTALES**: Salud financiera, PER, deuda y crecimiento esperado.
        3. 📉 **RIESGOS (BEAR CASE)**: Qué podría hacer que el valor caiga un 20% (sé muy crítico).
        4. 🎯 **VALORACIÓN Y PRECIO OBJETIVO**: Consenso de mercado vs precio actual.
        5. 💡 **ESTRATEGIA RECOMENDADA**: (Comprar/Vender/Mantener), precio de entrada ideal y horizonte temporal.

        Usa un tono profesional, cínico con las burbujas y muy analítico. No des consejos genéricos.
        """

        # Usamos Mistral Large con temperatura baja para máxima precisión
        response = await asyncio.to_thread(
            client.chat.complete,
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt_pro}],
            temperature=0.1
        )
        return response.choices[0].message.content

    except Exception as e:
        logging.error(f"Error en Deep Research: {e}")
        return f"❌ Falló el análisis profundo de {nombre_valor}. Error: {str(e)}"

async def buscar_oportunidades_inversion(mercado: str, client, buscar_internet):
    """Busca acciones con alto potencial de crecimiento en Nasdaq o Ibex."""
    try:
        # Definimos la búsqueda según el mercado
        if "nasdaq" in mercado.lower():
            query = "best growth stocks nasdaq 2026 high upside analyst ratings"
        else:
            query = "mejores acciones ibex 35 con potencial crecimiento 2026 dividendos y analistas"

        # 1. Buscamos en la web
        contexto = await asyncio.to_thread(buscar_internet, query)

        # 2. Le pedimos a Mistral Large que actúe como un Stock Picker
        prompt = f"""
        Eres un experto en Stock Picking. Basándote en esta información:
        {contexto}
        
        TAREA:
        Selecciona las 3 mejores oportunidades de inversión en {mercado.upper()}.
        Para cada una indica:
        - Ticker y Nombre.
        - Tesis de crecimiento (¿Por qué va a subir?).
        - Precio objetivo medio.
        - Nivel de riesgo (Bajo, Medio, Alto).
        
        ⚠️ Sé muy selectivo. Si no hay datos claros, adviértelo.
        """

        res = await asyncio.to_thread(
            client.chat.complete,
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return res.choices[0].message.content

    except Exception as e:
        logging.error(f"Error en escáner: {e}")
        return f"❌ No pude escanear el mercado {mercado} en este momento."

#--ASESON FINANCIERO--
def super_asesor_financiero(nombre_valor: str, client, buscar_internet):
    try:
        df = pd.read_excel("/app/documentos/bolsav2.xlsx", sheet_name='Operaciones')
        
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
