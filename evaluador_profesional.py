"""
EVALUADOR PROFESIONAL DE CARTERA - Nivel Hedge Fund
====================================================
Integra análisis técnico, fundamental, cuantitativo y sentimiento
para generar recomendaciones de inversión institucionales.
"""

import pandas as pd
import logging
import asyncio
import json
import traceback
from datetime import datetime
from tools_system import mistral_chat_with_retry
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

    @staticmethod
    def _to_float(value, default=0.0):
        try:
            if value is None:
                return default
            return float(str(value).replace('%', '').replace(',', '.').strip())
        except Exception:
            return default

    @staticmethod
    def _normalizar_ponderaciones(ponderacion: Dict) -> Dict:
        """Normaliza pesos de capas para mantener suma=1."""
        if not isinstance(ponderacion, dict):
            return {}

        claves = ['tecnico', 'fundamental', 'consenso', 'sentimiento', 'estrategico']
        valores = {k: max(0.0, EvaluadorProfesionalCartera._to_float(ponderacion.get(k), 0.0)) for k in claves}
        total = sum(valores.values())
        if total <= 0:
            return {k: round(1 / len(claves), 3) for k in claves}
        return {k: round(v / total, 3) for k, v in valores.items()}


    def _construir_contexto_estrategico(
        self,
        precio_compra: float,
        precio_actual: float,
        pct_ganancia: float,
        analisis_tecnico: Dict,
        metricas_fundamentales: Dict,
        consenso_analistas: Dict,
        sentimiento: Dict
    ) -> Dict:
        """Capa institucional: contexto de riesgo, valuación y asimetría tipo fondo estratégico."""
        volatilidad = self._to_float((analisis_tecnico or {}).get('volatilidad', {}).get('volatilidad_anual'), 30)
        per = self._to_float((metricas_fundamentales or {}).get('per'), 0)
        peg = self._to_float((metricas_fundamentales or {}).get('peg'), 2)
        deuda_patrimonio = self._to_float((metricas_fundamentales or {}).get('deuda_patrimonio'), 1)
        crecimiento_ingresos = self._to_float((metricas_fundamentales or {}).get('crecimiento_ingresos'), 0)
        score_sentimiento = self._to_float((sentimiento or {}).get('score'), 0)
        met_riesgo = (analisis_tecnico or {}).get('metricas_riesgo', {})
        sharpe = self._to_float((met_riesgo or {}).get('sharpe'), 0)
        max_dd = abs(self._to_float((met_riesgo or {}).get('max_drawdown_pct'), 0))
        precio_obj = self._to_float((consenso_analistas or {}).get('precio_objetivo_medio'), precio_actual)

        gap_consenso = ((precio_obj / precio_actual) - 1) * 100 if precio_actual > 0 else 0

        score_riesgo = min(
            100,
            max(0, (volatilidad * 1.0) + (deuda_patrimonio * 14) + (max(0, per - 25) * 1.1) + (max_dd * 0.35) - (crecimiento_ingresos * 0.7) - (max(0, sharpe) * 6))
        )
        conviccion = min(100, max(0, 55 + (gap_consenso * 0.35) + (score_sentimiento * 18) - (score_riesgo * 0.3)))

        if score_riesgo >= 70:
            bucket_riesgo = 'ALTO'
        elif score_riesgo >= 45:
            bucket_riesgo = 'MEDIO'
        else:
            bucket_riesgo = 'BAJO'

        if gap_consenso > 12 and score_riesgo <= 50:
            perfil = 'ASIMETRIA_FAVORABLE'
        elif gap_consenso < -8 or score_riesgo >= 70:
            perfil = 'ASIMETRIA_NEGATIVA'
        else:
            perfil = 'ASIMETRIA_NEUTRA'

        exposure_cap = 0.10
        if bucket_riesgo == 'MEDIO':
            exposure_cap = 0.07
        elif bucket_riesgo == 'ALTO':
            exposure_cap = 0.04

        if pct_ganancia <= -15 and bucket_riesgo == 'ALTO':
            exposure_cap = min(exposure_cap, 0.03)

        return {
            'bucket_riesgo': bucket_riesgo,
            'score_riesgo_cuant': round(score_riesgo, 1),
            'score_conviccion': round(conviccion, 1),
            'perfil_asimetria': perfil,
            'gap_consenso_pct': round(gap_consenso, 2),
            'limite_exposicion': exposure_cap,
            'peg': peg,
            'sharpe': round(sharpe, 2),
            'max_drawdown_pct': round(max_dd, 2)
        }

    def _ajustar_recomendacion_realista(self, recomendacion: Dict, contexto_estrategico: Dict, precio_actual: float) -> Dict:
        """Normaliza sesgos optimistas y aplica controles de riesgo institucionales."""
        rec = dict(recomendacion or {})

        upside = self._to_float(rec.get('upside_potencial'), 0)
        downside = abs(self._to_float(rec.get('downside_riesgo'), 0))
        riesgo_cuant = self._to_float(contexto_estrategico.get('score_riesgo_cuant'), 50)

        if upside > 45:
            upside = 45
        if downside == 0:
            downside = max(6, round(upside * 0.55, 1))
        elif downside > upside * 1.2 and upside > 0:
            upside = round(max(2.5, downside * 0.85), 1)

        if riesgo_cuant >= 70 and rec.get('accion') in ['COMPRAR', 'AUMENTAR']:
            rec['accion'] = 'MANTENER'
            rec['razon_principal'] = (
                "Se evita aumentar por riesgo elevado y asimetría limitada en el contexto actual."
            )

        rec['upside_potencial'] = round(upside, 1)
        rec['downside_riesgo'] = round(downside, 1)
        rec['contexto_estrategico'] = contexto_estrategico

        stop = self._to_float(rec.get('stop_loss'), 0)
        take = self._to_float(rec.get('take_profit'), 0)

        if precio_actual > 0:
            if stop <= 0:
                stop = precio_actual * (1 - min(0.18, max(0.06, downside / 100)))
            if take <= 0:
                take = precio_actual * (1 + min(0.35, max(0.08, upside / 100)))
            rec['stop_loss'] = round(stop, 2)
            rec['take_profit'] = round(take, 2)

        if rec.get('confianza_score') is not None:
            rec['confianza_score'] = min(0.82, max(0.35, self._to_float(rec.get('confianza_score'), 0.55)))

        return rec
    
    async def evaluar_cartera_completa(self, ruta_excel: str) -> Dict:
        """
        Evalúa todas las posiciones con análisis multi-capa en paralelo (máx 3 simultáneas).
        """
        try:
            logging.info("📊 Iniciando evaluación profesional de cartera...")

            df = await asyncio.to_thread(pd.read_excel, ruta_excel, sheet_name='Operaciones')
            activas = df[df.iloc[:, 8].isna()].copy()

            if activas.empty:
                return {'success': False, 'mensaje': "No hay inversiones activas para evaluar."}

            fecha_hoy = datetime.now().strftime("%d de %B de %Y")
            # Semaphore(1): evaluaciones secuenciales para respetar el rate limit de Tavily.
            # Cada evaluación ya hace ~11 llamadas internas; en paralelo dispararían el límite.
            semaforo = asyncio.Semaphore(1)

            async def _evaluar_fila(fila):
                async with semaforo:
                    nombre = str(fila.iloc[0])
                    precio_compra  = float(fila.iloc[5])  if pd.notna(fila.iloc[5])  else 0.0
                    num_acciones   = float(fila.iloc[4])  if pd.notna(fila.iloc[4])  else 0.0
                    valor_actual   = float(fila.iloc[9])  if pd.notna(fila.iloc[9])  else 0.0
                    ganancia_total = float(fila.iloc[14]) if pd.notna(fila.iloc[14]) else 0.0
                    pct_ganancia   = float(fila.iloc[15]) * 100 if pd.notna(fila.iloc[15]) else 0.0
                    logging.info(f"🔍 Evaluando {nombre} con análisis multi-capa...")
                    return await self._analizar_valor_completo(
                        nombre=nombre,
                        precio_compra=precio_compra,
                        num_acciones=num_acciones,
                        valor_actual=valor_actual,
                        ganancia_total=ganancia_total,
                        pct_ganancia=pct_ganancia,
                        fecha=fecha_hoy,
                    )

            resultados = await asyncio.gather(
                *[_evaluar_fila(activas.iloc[i]) for i in range(len(activas))],
                return_exceptions=True,
            )

            evaluaciones = []
            for r in resultados:
                if isinstance(r, Exception):
                    logging.error(f"❌ Error en evaluación de posición: {r}")
                else:
                    evaluaciones.append(r)

            resumen = self._generar_resumen_ejecutivo(evaluaciones)

            return {
                'success': True,
                'fecha': fecha_hoy,
                'total_posiciones': len(evaluaciones),
                'resumen': resumen,
                'evaluaciones': evaluaciones,
                'metodologia': 'Análisis Multi-Capa: Técnico + Fundamental + Consenso + Sentimiento + Capa Estratégica',
            }

        except Exception as e:
            logging.error(f"Error en evaluación profesional: {e}")
            traceback.print_exc()
            return {'success': False, 'mensaje': f"Error: {str(e)}"}

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
                'metodologia': 'Análisis Multi-Capa: Técnico + Fundamental + Consenso + Sentimiento + Capa Estratégica'
            }
        except Exception as e:
            logging.error(f"Error evaluando valor único: {e}")
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
                    'volatilidad': AnalizadorTecnicoAlgoritmico.calcular_volatilidad(precios_historicos),
                    'metricas_riesgo': AnalizadorTecnicoAlgoritmico.calcular_metricas_riesgo(precios_historicos)
                }
            else:
                logging.warning(f"  ⚠️ Datos técnicos insuficientes para {ticker}")
                analisis_tecnico = None
        except Exception as e:
            logging.error(f"  ❌ Error en análisis técnico: {e}")
            analisis_tecnico = None
        
        # Capas 2-4 SECUENCIALES — Tavily free tier: 1 req/seg.
        # asyncio.gather lanzaba llamadas en paralelo y saturaba el rate limit.
        logging.info(f"  💰 Capa 2: Fundamentales de {ticker}...")
        metricas_fundamentales = {}
        consenso_analistas = {}
        sentimiento = {'sentimiento': 'Neutral', 'score': 0}

        try:
            metricas_fundamentales = await self.buscador.obtener_metricas_fundamentales(ticker, nombre) or {}
        except Exception as e:
            logging.error(f"  ❌ Error en análisis fundamental: {e}")

        logging.info(f"  👔 Capa 3: Consenso de analistas de {ticker}...")
        try:
            consenso_analistas = await self.buscador.obtener_consenso_analistas(ticker, nombre) or {}
        except Exception as e:
            logging.error(f"  ❌ Error obteniendo consenso: {e}")

        logging.info(f"  📰 Capa 4: Sentimiento de {ticker}...")
        try:
            sentimiento = await self.buscador.analizar_sentimiento_noticias(ticker, nombre) or {'sentimiento': 'Neutral', 'score': 0}
        except Exception as e:
            logging.error(f"  ❌ Error en sentimiento: {e}")
        
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
        
        contexto_estrategico = self._construir_contexto_estrategico(
            precio_compra=precio_compra,
            precio_actual=precio_actual,
            pct_ganancia=pct_ganancia,
            analisis_tecnico=analisis_tecnico,
            metricas_fundamentales=metricas_fundamentales,
            consenso_analistas=consenso_analistas,
            sentimiento=sentimiento
        )

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

CAPA ESTRATÉGICA (MARCO FONDO INSTITUCIONAL):
- Bucket de riesgo: {contexto_estrategico['bucket_riesgo']} (score cuantitativo: {contexto_estrategico['score_riesgo_cuant']}/100)
- Convicción agregada: {contexto_estrategico['score_conviccion']}/100
- Perfil de asimetría: {contexto_estrategico['perfil_asimetria']}
- Gap vs consenso de analistas: {contexto_estrategico['gap_consenso_pct']:+.2f}%
- Límite sugerido de exposición por posición: {contexto_estrategico['limite_exposicion']:.0%}
"""
        
        # Prompt para síntesis profesional
        prompt = f"""{contexto}

TAREA: Como comité de inversión de un fondo long/short, sintetiza TODOS estos análisis y genera una recomendación final REALISTA.

CRITERIOS DE DECISIÓN:
1. Ponderar análisis técnico (25%), fundamental (35%), consenso (20%), sentimiento (10%), capa estratégica (10%)
2. Si hay señales conflictivas, priorizar datos más recientes y confiables
3. Considerar el contexto de la posición actual (ganancia/pérdida acumulada)
4. Aplicar gestión de riesgo profesional y sizing por límite de exposición
5. Evitar sesgo optimista: usa supuestos prudentes y reconoce incertidumbre

REGLAS ESTRICTAS:
- Si datos técnicos no disponibles → basar decisión en consenso analistas + fundamentales + sentimiento
- Si ganancia > +25% y señales técnicas de sobrecompra → TOMAR_BENEFICIOS (al menos parcial)
- Si pérdida > -20% y análisis negativo → CORTAR_PERDIDAS
- Si volatilidad MUY_ALTA + pérdidas → REDUCIR_EXPOSICION
- Si consenso Strong Buy + fundamentales sólidos (aunque no haya técnico) → MANTENER o COMPRAR
- Si solo hay datos parciales → usar "confianza": "BAJA" o "MEDIA", nunca forzar REDUCIR sin evidencia
- No proyectar upside >45% salvo evidencia excepcional cuantificada
- Si PER>40 y PEG>2 con crecimiento débil, NO recomendar COMPRAR agresivo
- Si datos insuficientes en 2 o más capas → accion: "INVESTIGAR" y razon explicando qué falta

Responde en JSON:
{{
  "accion": "COMPRAR|VENDER|MANTENER|REDUCIR|AUMENTAR|INVESTIGAR",
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
  "escenarios": {{
    "bajista": "impacto breve y condición de activación",
    "base": "caso central realista",
    "alcista": "escenario exigente pero plausible"
  }},
  "plan_ejecucion": {{
    "entrada": "condición de entrada o no entrada",
    "gestion": "cómo gestionar tamaño y riesgo",
    "salida": "criterios claros de salida"
  }},
  "ponderacion": {{
    "tecnico": 0.X,
    "fundamental": 0.X,
    "consenso": 0.X,
    "sentimiento": 0.X,
    "estrategico": 0.X
  }},
  "señal_tecnica": "ALCISTA|BAJISTA|NEUTRAL",
  "señal_fundamental": "POSITIVA|NEGATIVA|NEUTRAL",
  "nivel_precio": "INFRAVALORADO|JUSTO|SOBREVALORADO"
}}

Sé riguroso, concreto y sin marketing. Esta recomendación afecta dinero real.
"""
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.complete,
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,  # Baja temperatura para decisiones conservadoras
                response_format={"type": "json_object"}
            )
            recomendacion = json.loads(response.choices[0].message.content)
            recomendacion['ponderacion'] = self._normalizar_ponderaciones(recomendacion.get('ponderacion', {}))
            recomendacion = self._ajustar_recomendacion_realista(recomendacion, contexto_estrategico, precio_actual)
            
            logging.info(f"  ✅ Recomendación: {recomendacion.get('accion')} (Confianza: {recomendacion.get('confianza')})")
            
            return recomendacion
        
        except Exception as e:
            logging.error(f"Error sintetizando recomendación: {e}")
            return {
                'accion': 'ERROR',
                'razon_principal': f"No se pudo completar el análisis: {str(e)}",
                'contexto_estrategico': contexto_estrategico
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

**Metodología:** Análisis Multi-Capa (Técnico + Fundamental + Consenso + Sentimiento + Capa Estratégica)

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
    datos = ev.get('datos_posicion', {})
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
    precio_compra = _to_float_seguro(datos.get('precio_compra'))
    precio_actual = _to_float_seguro(datos.get('precio_actual'))
    ganancia_total = _to_float_seguro(datos.get('ganancia_total'))
    pct_ganancia = _to_float_seguro(datos.get('pct_ganancia'))

    msg += f"• Entrada: {precio_compra:.2f}€ | Actual: {precio_actual:.2f}€\n"
    msg += f"• P&L: {ganancia_total:,.2f}€ ({pct_ganancia:+.2f}%)\n\n"
    
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
    
    # Capa estratégica resumida
    cx = rec.get('contexto_estrategico', {})
    if cx:
        msg += "**Marco Estratégico:**\n"
        msg += f"• Riesgo Cuant: {cx.get('bucket_riesgo', 'N/A')} ({cx.get('score_riesgo_cuant', 'N/A')}/100)\n"
        msg += f"• Asimetría: {cx.get('perfil_asimetria', 'N/A')} | Gap consenso: {cx.get('gap_consenso_pct', 0):+.1f}%\n"
        msg += f"• Límite exposición sugerido: {cx.get('limite_exposicion', 0):.0%}\n\n"

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


def _to_float_seguro(valor, default=0.0):
    """Convierte a float de forma segura para evitar romper el formateo."""
    try:
        if valor is None:
            return float(default)
        return float(valor)
    except (TypeError, ValueError):
        return float(default)