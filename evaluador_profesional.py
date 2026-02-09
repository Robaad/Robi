"""
EVALUADOR PROFESIONAL DE CARTERA - Nivel Hedge Fund
====================================================
Integra análisis técnico, fundamental, cuantitativo y sentimiento
para generar recomendaciones de inversión institucionales.
"""

import pandas as pd
import logging
import asyncio
from datetime import datetime
from typing import Dict, List
from motor_cuantitativo import (
    AnalizadorTecnicoAlgoritmico,
    BuscadorDatosWeb
)


class EvaluadorProfesionalCartera:
    """
    Evaluador de cartera con metodología de hedge fund.
    
    Combina múltiples capas de análisis:
    1. Análisis Técnico Algorítmico
    2. Análisis Fundamental Profundo
    3. Consenso de Analistas Profesionales
    4. Análisis de Sentimiento
    5. Modelos Cuantitativos
    """
    
    def __init__(self, client, buscar_internet, modelo="mistral-large-latest"):
        self.client = client
        self.buscar = buscar_internet
        self.modelo = modelo
        self.buscador = BuscadorDatosWeb(buscar_internet, client, modelo)
    
    async def evaluar_cartera_completa(self, ruta_excel: str) -> Dict:
        """
        Evalúa todas las posiciones con análisis multi-capa.
        """
        try:
            logging.info("📊 Iniciando evaluación profesional de cartera...")
            
            # Leer Excel
            df = await asyncio.to_thread(pd.read_excel, ruta_excel, sheet_name='Operaciones')
            activas = df[df.iloc[:, 8].isna()].copy()
            
            if activas.empty:
                return {
                    'success': False,
                    'mensaje': "No hay inversiones activas para evaluar."
                }
            
            fecha_hoy = datetime.now().strftime("%d de %B de %Y")
            evaluaciones = []
            
            for i in range(len(activas)):
                fila = activas.iloc[i]
                
                nombre = str(fila.iloc[0])           # Columna A
                precio_compra = float(fila.iloc[5]) if pd.notna(fila.iloc[5]) else 0   # Columna F
                num_acciones = float(fila.iloc[4]) if pd.notna(fila.iloc[4]) else 0    # Columna E
                valor_actual = float(fila.iloc[9]) if pd.notna(fila.iloc[9]) else 0    # Columna J
                ganancia_total = float(fila.iloc[14]) if pd.notna(fila.iloc[14]) else 0 # Columna O
                pct_ganancia = float(fila.iloc[15]) * 100 if pd.notna(fila.iloc[15]) else 0  # Columna P
                
                logging.info(f"🔍 Evaluando {nombre} con análisis multi-capa...")
                
                # Análisis COMPLETO del valor
                evaluacion = await self._analizar_valor_completo(
                    nombre=nombre,
                    precio_compra=precio_compra,
                    num_acciones=num_acciones,
                    valor_actual=valor_actual,
                    ganancia_total=ganancia_total,
                    pct_ganancia=pct_ganancia,
                    fecha=fecha_hoy
                )
                
                evaluaciones.append(evaluacion)
            
            # Generar resumen ejecutivo
            resumen = self._generar_resumen_ejecutivo(evaluaciones)
            
            return {
                'success': True,
                'fecha': fecha_hoy,
                'total_posiciones': len(evaluaciones),
                'resumen': resumen,
                'evaluaciones': evaluaciones,
                'metodologia': 'Análisis Multi-Capa: Técnico + Fundamental + Consenso + Sentimiento'
            }
        
        except Exception as e:
            logging.error(f"Error en evaluación profesional: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'mensaje': f"Error: {str(e)}"
            }

    async def evaluar_valor_unico(self, valor: str) -> Dict:
        """
        Evalúa un único valor con el mismo análisis multi-capa.
        """
        try:
            nombre = valor.strip() or "Desconocido"
            ticker = nombre.split()[0] if nombre else "UNK"
            fecha_hoy = datetime.now().strftime("%d de %B de %Y")

            precios_historicos = await self.buscador.obtener_serie_precios(ticker)
            valor_actual = precios_historicos[-1] if precios_historicos else 0

            evaluacion = await self._analizar_valor_completo(
                nombre=nombre,
                precio_compra=valor_actual,
                num_acciones=0,
                valor_actual=valor_actual,
                ganancia_total=0,
                pct_ganancia=0,
                fecha=fecha_hoy
            )

            resumen = self._generar_resumen_ejecutivo([evaluacion])

            return {
                'success': True,
                'fecha': fecha_hoy,
                'total_posiciones': 1,
                'resumen': resumen,
                'evaluaciones': [evaluacion],
                'metodologia': 'Análisis Multi-Capa: Técnico + Fundamental + Consenso + Sentimiento'
            }
        except Exception as e:
            logging.error(f"Error evaluando valor único: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'mensaje': f"Error: {str(e)}"
            }
    
    async def _analizar_valor_completo(
        self,
        nombre: str,
        precio_compra: float,
        num_acciones: float,
        valor_actual: float,
        ganancia_total: float,
        pct_ganancia: float,
        fecha: str
    ) -> Dict:
        """
        Análisis completo de un valor con todas las capas.
        """
        
        # Extraer ticker del nombre (simplificado - mejorarlo según formato real)
        ticker = nombre.split()[0] if nombre else "UNK"
        
        logging.info(f"  📈 Capa 1: Análisis Técnico de {ticker}...")
        
        # CAPA 1: ANÁLISIS TÉCNICO ALGORÍTMICO
        try:
            precios_historicos = await self.buscador.obtener_serie_precios(ticker)
            
            if len(precios_historicos) >= 14:
                # Añadir precio actual si no está
                if valor_actual > 0 and (not precios_historicos or abs(precios_historicos[-1] - valor_actual) > 1):
                    precios_historicos.append(valor_actual)
                
                analisis_tecnico = {
                    'rsi': AnalizadorTecnicoAlgoritmico.calcular_rsi(precios_historicos),
                    'macd': AnalizadorTecnicoAlgoritmico.calcular_macd(precios_historicos),
                    'bollinger': AnalizadorTecnicoAlgoritmico.calcular_bollinger(precios_historicos),
                    'fibonacci': AnalizadorTecnicoAlgoritmico.calcular_niveles_fibonacci(precios_historicos),
                    'tendencia': AnalizadorTecnicoAlgoritmico.detectar_tendencia(precios_historicos),
                    'volatilidad': AnalizadorTecnicoAlgoritmico.calcular_volatilidad(precios_historicos)
                }
            else:
                logging.warning(f"  ⚠️ Datos técnicos insuficientes para {ticker}")
                analisis_tecnico = None
        except Exception as e:
            logging.error(f"  ❌ Error en análisis técnico: {e}")
            analisis_tecnico = None
        
        logging.info(f"  💰 Capa 2: Análisis Fundamental de {ticker}...")
        
        # CAPA 2: ANÁLISIS FUNDAMENTAL
        try:
            metricas_fundamentales = await self.buscador.obtener_metricas_fundamentales(ticker, nombre)
        except Exception as e:
            logging.error(f"  ❌ Error en análisis fundamental: {e}")
            metricas_fundamentales = {}
        
        logging.info(f"  👔 Capa 3: Consenso de Analistas de {ticker}...")
        
        # CAPA 3: CONSENSO DE ANALISTAS
        try:
            consenso_analistas = await self.buscador.obtener_consenso_analistas(ticker, nombre)
        except Exception as e:
            logging.error(f"  ❌ Error obteniendo consenso: {e}")
            consenso_analistas = {}
        
        logging.info(f"  📰 Capa 4: Análisis de Sentimiento de {ticker}...")
        
        # CAPA 4: ANÁLISIS DE SENTIMIENTO
        try:
            sentimiento = await self.buscador.analizar_sentimiento_noticias(ticker, nombre)
        except Exception as e:
            logging.error(f"  ❌ Error en sentimiento: {e}")
            sentimiento = {'sentimiento': 'Neutral', 'score': 0}
        
        logging.info(f"  🧮 Capa 5: Síntesis y Recomendación Final de {ticker}...")
        
        # CAPA 5: SÍNTESIS Y RECOMENDACIÓN FINAL
        recomendacion_final = await self._sintetizar_recomendacion(
            ticker=ticker,
            nombre=nombre,
            precio_compra=precio_compra,
            precio_actual=valor_actual,
            ganancia_total=ganancia_total,
            pct_ganancia=pct_ganancia,
            analisis_tecnico=analisis_tecnico,
            metricas_fundamentales=metricas_fundamentales,
            consenso_analistas=consenso_analistas,
            sentimiento=sentimiento
        )
        
        return {
            'nombre': nombre,
            'ticker': ticker,
            'datos_posicion': {
                'precio_compra': precio_compra,
                'precio_actual': valor_actual,
                'num_acciones': num_acciones,
                'ganancia_total': ganancia_total,
                'pct_ganancia': pct_ganancia
            },
            'analisis_tecnico': analisis_tecnico,
            'metricas_fundamentales': metricas_fundamentales,
            'consenso_analistas': consenso_analistas,
            'sentimiento': sentimiento,
            'recomendacion': recomendacion_final
        }
    
    async def _sintetizar_recomendacion(
        self,
        ticker: str,
        nombre: str,
        precio_compra: float,
        precio_actual: float,
        ganancia_total: float,
        pct_ganancia: float,
        analisis_tecnico: Dict,
        metricas_fundamentales: Dict,
        consenso_analistas: Dict,
        sentimiento: Dict
    ) -> Dict:
        """
        Sintetiza todos los análisis en una recomendación final.
        Usa IA para ponderar las señales conflictivas.
        """
        
        # Construir contexto para la IA
        contexto = f"""ANÁLISIS COMPLETO DE {ticker} - {nombre}

POSICIÓN ACTUAL:
- Precio compra: {precio_compra:.2f}€
- Precio actual: {precio_actual:.2f}€
- Ganancia/Pérdida: {ganancia_total:,.2f}€ ({pct_ganancia:+.2f}%)

ANÁLISIS TÉCNICO:
"""
        
        if analisis_tecnico:
            contexto += f"""
- RSI: {analisis_tecnico.get('rsi', {}).get('valor', 'N/A')} - {analisis_tecnico.get('rsi', {}).get('señal', 'N/A')}
  Acción: {analisis_tecnico.get('rsi', {}).get('accion', 'N/A')}
  
- MACD: {analisis_tecnico.get('macd', {}).get('señal', 'N/A')}
  Acción: {analisis_tecnico.get('macd', {}).get('accion', 'N/A')}
  
- Bollinger: {analisis_tecnico.get('bollinger', {}).get('señal', 'N/A')}
  {analisis_tecnico.get('bollinger', {}).get('interpretacion', '')}
  
- Tendencia: {analisis_tecnico.get('tendencia', {}).get('tendencia', 'N/A')} (Fuerza: {analisis_tecnico.get('tendencia', {}).get('fuerza', 0)})
  {analisis_tecnico.get('tendencia', {}).get('interpretacion', '')}
  
- Volatilidad: {analisis_tecnico.get('volatilidad', {}).get('volatilidad_anual', 'N/A')}% anual - Riesgo {analisis_tecnico.get('volatilidad', {}).get('riesgo', 'N/A')}

- Fibonacci (Soportes/Resistencias):
  Nivel cercano: {analisis_tecnico.get('fibonacci', {}).get('nivel_cercano', 'N/A')} en {analisis_tecnico.get('fibonacci', {}).get('precio_nivel', 'N/A')}€
"""
        else:
            contexto += "\n- Datos técnicos no disponibles\n"
        
        contexto += f"""
ANÁLISIS FUNDAMENTAL:
- PER: {metricas_fundamentales.get('per', 'N/A')}
- PEG: {metricas_fundamentales.get('peg', 'N/A')}
- ROE: {metricas_fundamentales.get('roe', 'N/A')}%
- Deuda/Patrimonio: {metricas_fundamentales.get('deuda_patrimonio', 'N/A')}
- Margen Operativo: {metricas_fundamentales.get('margen_operativo', 'N/A')}%
- Crecimiento Ingresos: {metricas_fundamentales.get('crecimiento_ingresos', 'N/A')}%
- FCF: {metricas_fundamentales.get('fcf', 'N/A')}
- Dividend Yield: {metricas_fundamentales.get('dividend_yield', 'N/A')}%
- Valoración: {metricas_fundamentales.get('valoracion', 'N/A')}

CONSENSO ANALISTAS:
- Recomendación: {consenso_analistas.get('recomendacion', 'N/A')}
- Nº Analistas: {consenso_analistas.get('num_analistas', 'N/A')}
- Precio Objetivo Medio: {consenso_analistas.get('precio_objetivo_medio', 'N/A')}€
- Rango: {consenso_analistas.get('precio_objetivo_bajo', 'N/A')}€ - {consenso_analistas.get('precio_objetivo_alto', 'N/A')}€
- Distribución: {consenso_analistas.get('comprar', 0)} Comprar, {consenso_analistas.get('mantener', 0)} Mantener, {consenso_analistas.get('vender', 0)} Vender

ANÁLISIS DE SENTIMIENTO:
- Sentimiento: {sentimiento.get('sentimiento', 'Neutral')} (Score: {sentimiento.get('score', 0)})
- Catalizadores Positivos: {', '.join(sentimiento.get('catalizadores_positivos', []))}
- Riesgos: {', '.join(sentimiento.get('riesgos', []))}
- Eventos Próximos: {', '.join(sentimiento.get('eventos_proximos', []))}
"""
        
        # Prompt para síntesis profesional
        prompt = f"""{contexto}

TAREA: Como gestor profesional de un hedge fund, sintetiza TODOS estos análisis y genera una recomendación final.

CRITERIOS DE DECISIÓN:
1. Ponderar análisis técnico (30%), fundamental (30%), consenso (25%), sentimiento (15%)
2. Si hay señales conflictivas, priorizar datos más recientes y confiables
3. Considerar el contexto de la posición actual (ganancia/pérdida acumulada)
4. Aplicar gestión de riesgo profesional

REGLAS ESTRICTAS:
- Si ganancia > +25% y señales técnicas de sobrecompra → TOMAR_BENEFICIOS (al menos parcial)
- Si pérdida > -20% y análisis negativo → CORTAR_PERDIDAS
- Si volatilidad MUY_ALTA + pérdidas → REDUCIR_EXPOSICION
- Si consenso Strong Buy + técnico alcista + fundamentales sólidos → MANTENER o AUMENTAR

Responde en JSON:
{{
  "accion": "COMPRAR|VENDER|MANTENER|REDUCIR|AUMENTAR",
  "confianza": "MUY_ALTA|ALTA|MEDIA|BAJA",
  "confianza_score": 0.X,
  "precio_objetivo_6m": valor,
  "precio_objetivo_12m": valor,
  "stop_loss": valor,
  "take_profit": valor,
  "upside_potencial": porcentaje,
  "downside_riesgo": porcentaje,
  "riesgo": "MUY_BAJO|BAJO|MEDIO|ALTO|MUY_ALTO",
  "horizonte": "CORTO_PLAZO|MEDIO_PLAZO|LARGO_PLAZO",
  "razon_principal": "Razón clara en 1 frase (máx 150 chars)",
  "argumentos_principales": ["Argumento 1", "Argumento 2", "Argumento 3"],
  "riesgos_principales": ["Riesgo 1", "Riesgo 2"],
  "ponderacion": {{
    "tecnico": 0.X,
    "fundamental": 0.X,
    "consenso": 0.X,
    "sentimiento": 0.X
  }},
  "señal_tecnica": "ALCISTA|BAJISTA|NEUTRAL",
  "señal_fundamental": "POSITIVA|NEGATIVA|NEUTRAL",
  "nivel_precio": "INFRAVALORADO|JUSTO|SOBREVALORADO"
}}

Sé riguroso y profesional. Esta recomendación afecta dinero real.
"""
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.complete,
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,  # Baja temperatura para decisiones conservadoras
                response_format={"type": "json_object"}
            )
            
            import json
            recomendacion = json.loads(response.choices[0].message.content)
            
            logging.info(f"  ✅ Recomendación: {recomendacion.get('accion')} (Confianza: {recomendacion.get('confianza')})")
            
            return recomendacion
        
        except Exception as e:
            logging.error(f"Error sintetizando recomendación: {e}")
            return {
                'accion': 'ERROR',
                'razon_principal': f"No se pudo completar el análisis: {str(e)}"
            }
    
    def _generar_resumen_ejecutivo(self, evaluaciones: List[Dict]) -> str:
        """Genera resumen ejecutivo tipo hedge fund."""
        
        total = len(evaluaciones)
        
        # Contadores por acción
        acciones = {}
        for ev in evaluaciones:
            accion = ev['recomendacion'].get('accion', 'ERROR')
            acciones[accion] = acciones.get(accion, 0) + 1
        
        # Riesgo total de cartera
        riesgos = {}
        for ev in evaluaciones:
            riesgo = ev['recomendacion'].get('riesgo', 'MEDIO')
            riesgos[riesgo] = riesgos.get(riesgo, 0) + 1
        
        # Upside promedio ponderado
        upsides = []
        for ev in evaluaciones:
            upside = ev['recomendacion'].get('upside_potencial', 0)
            if upside:
                try:
                    upsides.append(float(upside))
                except:
                    pass
        
        upside_promedio = sum(upsides) / len(upsides) if upsides else 0
        
        # Recomendaciones urgentes
        urgentes = [
            ev for ev in evaluaciones
            if ev['recomendacion'].get('accion') in ['VENDER', 'REDUCIR']
            and ev['recomendacion'].get('confianza') in ['MUY_ALTA', 'ALTA']
        ]
        
        resumen = f"""📊 **RESUMEN EJECUTIVO - ANÁLISIS PROFESIONAL**

**Metodología:** Análisis Multi-Capa (Técnico + Fundamental + Consenso + Sentimiento)

**Posiciones Analizadas:** {total}

**Distribución de Recomendaciones:**
"""
        
        for accion, count in sorted(acciones.items(), key=lambda x: x[1], reverse=True):
            icono = {'COMPRAR': '🟢', 'AUMENTAR': '🟢', 'MANTENER': '🟡', 'REDUCIR': '🟠', 'VENDER': '🔴'}.get(accion, '⚪')
            pct = (count / total) * 100
            resumen += f"• {icono} {accion}: {count} posición(es) ({pct:.0f}%)\n"
        
        resumen += f"""
**Perfil de Riesgo de Cartera:**
"""
        for riesgo, count in sorted(riesgos.items()):
            resumen += f"• {riesgo}: {count} valor(es)\n"
        
        resumen += f"""
**Potencial de Retorno:**
• Upside promedio ponderado: {upside_promedio:+.1f}%
"""
        
        if urgentes:
            resumen += f"\n🚨 **ATENCIÓN URGENTE:** {len(urgentes)} posición(es) requieren acción inmediata\n"
            for ev in urgentes[:3]:  # Mostrar hasta 3
                nombre = ev.get('nombre', 'Desconocido')
                accion = ev['recomendacion'].get('accion')
                razon = ev['recomendacion'].get('razon_principal', '')
                resumen += f"   • {nombre}: {accion} - {razon}\n"
        
        return resumen


def formatear_informe_profesional(resultado: Dict) -> str:
    """
    Formatea el informe completo estilo hedge fund.
    """
    
    if not resultado.get('success'):
        return f"❌ {resultado.get('mensaje', 'Error desconocido')}"
    
    fecha = resultado.get('fecha', 'N/A')
    total = resultado.get('total_posiciones', 0)
    
    # Encabezado
    msg = f"""📊 **EVALUACIÓN PROFESIONAL DE CARTERA**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fecha: {fecha}
Posiciones: {total}
Metodología: {resultado.get('metodologia', 'N/A')}

"""
    
    # Resumen ejecutivo
    msg += resultado.get('resumen', '')
    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "**ANÁLISIS DETALLADO POR VALOR:**\n\n"
    
    # Evaluaciones individuales
    evaluaciones = resultado.get('evaluaciones', [])
    
    # Ordenar por urgencia (VENDER/REDUCIR primero)
    orden_accion = {'VENDER': 0, 'REDUCIR': 1, 'COMPRAR': 2, 'AUMENTAR': 3, 'MANTENER': 4, 'ERROR': 5}
    evaluaciones_ordenadas = sorted(
        evaluaciones,
        key=lambda x: orden_accion.get(x['recomendacion'].get('accion', 'ERROR'), 5)
    )
    
    for ev in evaluaciones_ordenadas:
        msg += formatear_evaluacion_individual_profesional(ev)
        msg += "\n"
    
    # Footer
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ **DISCLAIMER:** Análisis generado con metodología cuantitativa profesional. "
    msg += "No constituye asesoramiento financiero personalizado. Consulta con tu asesor antes de operar.\n"
    
    return msg


def formatear_evaluacion_individual_profesional(ev: Dict) -> str:
    """Formatea evaluación individual estilo profesional."""
    
    nombre = ev.get('nombre', 'Desconocido')
    ticker = ev.get('ticker', '')
    datos = ev['datos_posicion']
    rec = ev['recomendacion']
    
    # Icono según acción
    accion_icons = {
        'VENDER': '🔴',
        'REDUCIR': '🟠',
        'MANTENER': '🟡',
        'AUMENTAR': '🟢',
        'COMPRAR': '🟢'
    }
    icono = accion_icons.get(rec.get('accion', 'ERROR'), '⚪')
    
    msg = f"{icono} **{nombre}** ({ticker})\n"
    msg += f"{'─' * 40}\n"
    
    # Posición actual
    msg += f"**Posición:**\n"
    msg += f"• Entrada: {datos['precio_compra']:.2f}€ | Actual: {datos['precio_actual']:.2f}€\n"
    msg += f"• P&L: {datos['ganancia_total']:,.2f}€ ({datos['pct_ganancia']:+.2f}%)\n\n"
    
    # Recomendación principal
    msg += f"**Recomendación:** {rec.get('accion')} "
    msg += f"(Confianza: {rec.get('confianza')} - {rec.get('confianza_score', 0):.0%})\n"
    msg += f"**Razón:** {rec.get('razon_principal', 'N/A')}\n\n"
    
    # Precios objetivo
    if rec.get('precio_objetivo_12m'):
        msg += f"**Valoración:**\n"
        msg += f"• Objetivo 6M: {rec.get('precio_objetivo_6m', 0):.2f}€\n"
        msg += f"• Objetivo 12M: {rec.get('precio_objetivo_12m', 0):.2f}€\n"
        msg += f"• Stop Loss: {rec.get('stop_loss', 0):.2f}€\n"
        msg += f"• Take Profit: {rec.get('take_profit', 0):.2f}€\n"
        msg += f"• Upside: {rec.get('upside_potencial', 0):+.1f}% | Downside: {rec.get('downside_riesgo', 0):.1f}%\n\n"
    
    # Análisis técnico resumido
    if ev.get('analisis_tecnico'):
        at = ev['analisis_tecnico']
        msg += f"**Señales Técnicas:**\n"
        msg += f"• RSI: {at.get('rsi', {}).get('señal', 'N/A')} ({at.get('rsi', {}).get('valor', 'N/A')})\n"
        msg += f"• Tendencia: {at.get('tendencia', {}).get('tendencia', 'N/A')}\n"
        msg += f"• Volatilidad: {at.get('volatilidad', {}).get('riesgo', 'N/A')}\n\n"
    
    # Fundamentales clave
    if ev.get('metricas_fundamentales'):
        mf = ev['metricas_fundamentales']
        msg += f"**Fundamentales:**\n"
        if mf.get('per'):
            msg += f"• PER: {mf.get('per')} | "
        if mf.get('roe'):
            msg += f"ROE: {mf.get('roe')}%\n"
        if mf.get('valoracion'):
            msg += f"• Valoración: {mf.get('valoracion').upper()}\n"
        msg += "\n"
    
    # Argumentos principales
    if rec.get('argumentos_principales'):
        args = rec['argumentos_principales'][:2]  # Max 2
        msg += f"**Tesis:** {' | '.join(args)}\n"
    
    # Riesgos
    if rec.get('riesgos_principales'):
        riesgos = rec['riesgos_principales'][:2]  # Max 2
        msg += f"**Riesgos:** {' | '.join(riesgos)}\n"
    
    msg += f"\n**Nivel de Riesgo:** {rec.get('riesgo', 'N/A')}\n"
    
    return msg
