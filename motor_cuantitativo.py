"""
MOTOR DE ANÁLISIS CUANTITATIVO - Nivel Hedge Fund
==================================================
Sistema profesional de análisis de valores que combina:
- Análisis fundamental profundo (PER, PEG, ROE, FCF, márgenes)
- Análisis técnico algorítmico (RSI, MACD, Bollinger, Fibonacci)
- Modelos cuantitativos (Sharpe, Sortino, Beta, Alpha)
- Análisis de sentimiento de noticias
- Valoración por múltiplos y DCF
- Consenso de analistas profesionales
"""

import numpy as np
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import re
import requests


class AnalizadorTecnicoAlgoritmico:
    """
    Análisis técnico usando algoritmos profesionales.
    Implementa los mismos indicadores que usan los hedge funds.
    """
    
    @staticmethod
    def calcular_rsi(precios: List[float], periodo: int = 14) -> Dict:
        """
        RSI (Relative Strength Index) - Indicador de momentum.
        
        Interpretación:
        - RSI > 70: Sobrecompra (posible corrección)
        - RSI < 30: Sobreventa (posible rebote)
        - RSI 50-70: Alcista saludable
        - RSI 30-50: Bajista moderado
        """
        if len(precios) < periodo + 1:
            return {'valor': 50, 'señal': 'NEUTRAL', 'datos_insuficientes': True}
        
        deltas = np.diff(precios)
        ganancia = np.where(deltas > 0, deltas, 0)
        perdida = np.where(deltas < 0, -deltas, 0)
        
        avg_ganancia = np.mean(ganancia[-periodo:])
        avg_perdida = np.mean(perdida[-periodo:])
        
        if avg_perdida == 0:
            rsi = 100
        else:
            rs = avg_ganancia / avg_perdida
            rsi = 100 - (100 / (1 + rs))
        
        # Señales de trading
        if rsi > 80:
            señal = "SOBRECOMPRA_EXTREMA"
            accion = "VENDER"
            confianza = 0.85
        elif rsi > 70:
            señal = "SOBRECOMPRA"
            accion = "TOMAR_BENEFICIOS"
            confianza = 0.70
        elif rsi < 20:
            señal = "SOBREVENTA_EXTREMA"
            accion = "COMPRAR"
            confianza = 0.85
        elif rsi < 30:
            señal = "SOBREVENTA"
            accion = "ACUMULAR"
            confianza = 0.70
        elif 45 <= rsi <= 55:
            señal = "NEUTRAL"
            accion = "ESPERAR"
            confianza = 0.50
        elif rsi > 55:
            señal = "ALCISTA"
            accion = "MANTENER"
            confianza = 0.60
        else:
            señal = "BAJISTA"
            accion = "VIGILAR"
            confianza = 0.60
        
        return {
            'valor': round(rsi, 2),
            'señal': señal,
            'accion': accion,
            'confianza': confianza,
            'interpretacion': f"RSI en {rsi:.1f} indica {señal.lower().replace('_', ' ')}"
        }
    
    @staticmethod
    def calcular_macd(precios: List[float]) -> Dict:
        """
        MACD (Moving Average Convergence Divergence).
        
        Detecta cambios en momentum y posibles reversiones.
        """
        if len(precios) < 26:
            return {'señal': 'NEUTRAL', 'datos_insuficientes': True}
        
        precios_arr = np.array(precios, dtype=float)

        # Cálculo profesional: MACD como diferencia entre series EMA
        ema_12_series = AnalizadorTecnicoAlgoritmico._ema_series(precios_arr, 12)
        ema_26_series = AnalizadorTecnicoAlgoritmico._ema_series(precios_arr, 26)
        macd_series = ema_12_series - ema_26_series
        signal_series = AnalizadorTecnicoAlgoritmico._ema_series(macd_series, 9)

        macd_line = float(macd_series[-1])
        signal_line = float(signal_series[-1])
        histograma = macd_line - signal_line
        
        # Señales
        if histograma > 0 and abs(histograma) > abs(macd_line) * 0.1:
            señal = "CRUCE_ALCISTA"
            accion = "COMPRAR"
            confianza = 0.75
        elif histograma < 0 and abs(histograma) > abs(macd_line) * 0.1:
            señal = "CRUCE_BAJISTA"
            accion = "VENDER"
            confianza = 0.75
        elif macd_line > 0:
            señal = "MOMENTUM_POSITIVO"
            accion = "MANTENER"
            confianza = 0.60
        elif macd_line < 0:
            señal = "MOMENTUM_NEGATIVO"
            accion = "VIGILAR"
            confianza = 0.60
        else:
            señal = "NEUTRAL"
            accion = "ESPERAR"
            confianza = 0.50
        
        return {
            'macd': round(macd_line, 4),
            'signal': round(signal_line, 4),
            'histograma': round(histograma, 4),
            'señal': señal,
            'accion': accion,
            'confianza': confianza
        }
    
    @staticmethod
    def calcular_bollinger(precios: List[float], periodo: int = 20) -> Dict:
        """
        Bandas de Bollinger - Detectan volatilidad y sobreextensión.
        """
        if len(precios) < periodo:
            return {'señal': 'NEUTRAL', 'datos_insuficientes': True}
        
        precios_arr = np.array(precios[-periodo:])
        sma = np.mean(precios_arr)
        std = np.std(precios_arr)
        
        banda_superior = sma + (2 * std)
        banda_media = sma
        banda_inferior = sma - (2 * std)
        
        precio_actual = precios[-1]
        
        # Calcular posición relativa (0-1)
        ancho_banda = banda_superior - banda_inferior
        posicion = (precio_actual - banda_inferior) / ancho_banda if ancho_banda > 0 else 0.5
        
        # Señales
        if precio_actual > banda_superior:
            señal = "SOBREEXTENDIDO_ALCISTA"
            accion = "TOMAR_BENEFICIOS"
            confianza = 0.70
            interpretacion = "Precio fuera de banda superior - sobrecomprado"
        elif precio_actual < banda_inferior:
            señal = "SOBREEXTENDIDO_BAJISTA"
            accion = "COMPRAR_OPORTUNIDAD"
            confianza = 0.70
            interpretacion = "Precio fuera de banda inferior - sobrevendido"
        elif posicion > 0.8:
            señal = "CERCA_RESISTENCIA"
            accion = "VIGILAR"
            confianza = 0.60
            interpretacion = "Acercándose a banda superior"
        elif posicion < 0.2:
            señal = "CERCA_SOPORTE"
            accion = "ACUMULAR"
            confianza = 0.60
            interpretacion = "Acercándose a banda inferior"
        else:
            señal = "RANGO_NORMAL"
            accion = "MANTENER"
            confianza = 0.50
            interpretacion = "Precio dentro de bandas normales"
        
        # Squeeze (baja volatilidad) - precede movimientos fuertes
        ancho_relativo = (banda_superior - banda_inferior) / banda_media
        squeeze = ancho_relativo < 0.1
        
        return {
            'banda_superior': round(banda_superior, 2),
            'banda_media': round(banda_media, 2),
            'banda_inferior': round(banda_inferior, 2),
            'precio_actual': round(precio_actual, 2),
            'posicion_relativa': round(posicion, 2),
            'señal': señal,
            'accion': accion,
            'confianza': confianza,
            'squeeze': squeeze,
            'interpretacion': interpretacion
        }
    
    @staticmethod
    def calcular_niveles_fibonacci(precios: List[float]) -> Dict:
        """
        Niveles de Fibonacci - Soportes y resistencias clave.
        
        Usado por traders profesionales para identificar zonas de reversión.
        """
        if len(precios) < 10:
            return {'niveles': {}, 'datos_insuficientes': True}
        
        max_precio = max(precios)
        min_precio = min(precios)
        diferencia = max_precio - min_precio
        
        # Niveles de Fibonacci clásicos
        niveles = {
            '100%': round(max_precio, 2),
            '78.6%': round(max_precio - (diferencia * 0.214), 2),
            '61.8%': round(max_precio - (diferencia * 0.382), 2),
            '50%': round(max_precio - (diferencia * 0.5), 2),
            '38.2%': round(max_precio - (diferencia * 0.618), 2),
            '23.6%': round(max_precio - (diferencia * 0.764), 2),
            '0%': round(min_precio, 2)
        }
        
        precio_actual = precios[-1]
        
        # Identificar nivel más cercano
        distancias = {k: abs(v - precio_actual) for k, v in niveles.items()}
        nivel_cercano = min(distancias, key=distancias.get)
        distancia_pct = (distancias[nivel_cercano] / precio_actual) * 100
        
        # Determinar si está en soporte o resistencia
        if precio_actual > niveles['50%']:
            zona = "RESISTENCIAS"
            niveles_clave = ['61.8%', '78.6%', '100%']
        else:
            zona = "SOPORTES"
            niveles_clave = ['38.2%', '23.6%', '0%']
        
        return {
            'niveles': niveles,
            'nivel_cercano': nivel_cercano,
            'precio_nivel': niveles[nivel_cercano],
            'distancia_pct': round(distancia_pct, 2),
            'zona': zona,
            'niveles_clave': [niveles[k] for k in niveles_clave],
            'accion': f"Vigilar nivel {nivel_cercano} en {niveles[nivel_cercano]}€"
        }
    
    @staticmethod
    def detectar_tendencia(precios: List[float]) -> Dict:
        """
        Detecta tendencia mediante análisis de medias móviles.
        
        Golden Cross / Death Cross son señales muy fuertes.
        """
        if len(precios) < 50:
            sma_50 = np.mean(precios)
            sma_200 = np.mean(precios)
            datos_limitados = True
        else:
            sma_50 = np.mean(precios[-50:])
            sma_200 = np.mean(precios[-200:]) if len(precios) >= 200 else np.mean(precios)
            datos_limitados = False
        
        precio_actual = precios[-1]
        
        # Análisis de posición
        sobre_sma50 = precio_actual > sma_50
        sobre_sma200 = precio_actual > sma_200
        golden_cross = sma_50 > sma_200
        
        # Determinar tendencia
        if golden_cross and sobre_sma50 and sobre_sma200:
            tendencia = "ALCISTA_FUERTE"
            fuerza = 0.90
            accion = "COMPRAR/MANTENER"
            interpretacion = "Golden Cross confirmado - tendencia alcista sólida"
        elif not golden_cross and not sobre_sma50 and not sobre_sma200:
            tendencia = "BAJISTA_FUERTE"
            fuerza = 0.90
            accion = "VENDER/EVITAR"
            interpretacion = "Death Cross confirmado - tendencia bajista sólida"
        elif sobre_sma50:
            tendencia = "ALCISTA_MODERADA"
            fuerza = 0.65
            accion = "MANTENER"
            interpretacion = "Precio sobre media de 50 días - momentum positivo"
        elif not sobre_sma50:
            tendencia = "BAJISTA_MODERADA"
            fuerza = 0.65
            accion = "VIGILAR"
            interpretacion = "Precio bajo media de 50 días - momentum negativo"
        else:
            tendencia = "LATERAL"
            fuerza = 0.50
            accion = "ESPERAR"
            interpretacion = "Sin tendencia clara definida"
        
        return {
            'tendencia': tendencia,
            'fuerza': fuerza,
            'sma_50': round(sma_50, 2),
            'sma_200': round(sma_200, 2),
            'precio_actual': round(precio_actual, 2),
            'golden_cross': golden_cross,
            'accion': accion,
            'interpretacion': interpretacion,
            'datos_limitados': datos_limitados
        }
    
    @staticmethod
    def calcular_volatilidad(precios: List[float]) -> Dict:
        """
        Volatilidad anualizada - Medida de riesgo clave.
        """
        if len(precios) < 2:
            return {'volatilidad_anual': 0, 'riesgo': 'DESCONOCIDO'}
        
        returns = np.diff(precios) / precios[:-1]
        volatilidad_diaria = np.std(returns)
        volatilidad_anual = volatilidad_diaria * np.sqrt(252) * 100  # 252 días de trading
        
        # Clasificación de riesgo
        if volatilidad_anual > 50:
            nivel = "MUY_ALTA"
            riesgo = "EXTREMO"
            accion = "Solo para traders experimentados"
        elif volatilidad_anual > 35:
            nivel = "ALTA"
            riesgo = "ALTO"
            accion = "Requiere gestión activa de riesgo"
        elif volatilidad_anual > 20:
            nivel = "MODERADA"
            riesgo = "MEDIO"
            accion = "Volatilidad típica de mercado"
        elif volatilidad_anual > 10:
            nivel = "BAJA"
            riesgo = "BAJO"
            accion = "Relativamente estable"
        else:
            nivel = "MUY_BAJA"
            riesgo = "MUY_BAJO"
            accion = "Muy estable, posible blue chip"
        
        return {
            'volatilidad_anual': round(volatilidad_anual, 2),
            'nivel': nivel,
            'riesgo': riesgo,
            'accion': accion
        }

    @staticmethod
    def calcular_metricas_riesgo(precios: List[float]) -> Dict:
        """
        Capa cuantitativa institucional: VaR/CVaR, drawdown y ratios ajustados a riesgo.
        """
        if len(precios) < 30:
            return {'datos_insuficientes': True}

        precios_arr = np.array(precios, dtype=float)
        returns = np.diff(precios_arr) / precios_arr[:-1]

        if len(returns) < 2:
            return {'datos_insuficientes': True}

        mean_daily = float(np.mean(returns))
        rf_daily = 0.02 / 252
        excess_daily = returns - rf_daily

        std_daily = float(np.std(returns))
        downside = returns[returns < 0]
        downside_std = float(np.std(downside)) if len(downside) > 1 else 0.0

        sharpe = (mean_daily - rf_daily) / std_daily * np.sqrt(252) if std_daily > 0 else 0.0
        sortino = (mean_daily - rf_daily) / downside_std * np.sqrt(252) if downside_std > 0 else 0.0

        curva = np.cumprod(1 + returns)
        max_curve = np.maximum.accumulate(curva)
        drawdowns = (curva - max_curve) / max_curve
        max_drawdown = float(np.min(drawdowns)) * 100

        anual_return = ((1 + mean_daily) ** 252 - 1) * 100
        calmar = anual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

        var_95 = float(np.percentile(returns, 5)) * 100
        cvar_95 = float(np.mean(returns[returns <= np.percentile(returns, 5)])) * 100

        tracking_error = float(np.std(excess_daily)) * np.sqrt(252) * 100

        return {
            'sharpe': round(sharpe, 2),
            'sortino': round(sortino, 2),
            'calmar': round(calmar, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'var_95_pct_dia': round(var_95, 2),
            'cvar_95_pct_dia': round(cvar_95, 2),
            'tracking_error_anual_pct': round(tracking_error, 2),
            'retorno_anualizado_pct': round(anual_return, 2)
        }
    
    @staticmethod
    def _ema(precios: np.ndarray, periodo: int) -> float:
        """Calcula Exponential Moving Average."""
        if len(precios) < periodo:
            return float(np.mean(precios))
        
        multiplier = 2 / (periodo + 1)
        ema = float(np.mean(precios[:periodo]))
        
        for precio in precios[periodo:]:
            ema = (float(precio) * multiplier) + (ema * (1 - multiplier))
        
        return ema

    @staticmethod
    def _ema_series(precios: np.ndarray, periodo: int) -> np.ndarray:
        """Calcula toda la serie EMA para señales más estables."""
        if len(precios) == 0:
            return np.array([])
        if len(precios) < periodo:
            return np.full(len(precios), float(np.mean(precios)))

        multiplier = 2 / (periodo + 1)
        ema_values = np.zeros(len(precios), dtype=float)
        ema_values[0] = float(precios[0])

        for i in range(1, len(precios)):
            ema_values[i] = (float(precios[i]) * multiplier) + (ema_values[i - 1] * (1 - multiplier))

        return ema_values


class BuscadorDatosWeb:
    """
    Busca datos específicos en internet de forma estructurada.
    Extrae información de múltiples fuentes.
    """
    
    def __init__(self, buscar_internet_fn, client, modelo):
        self.buscar = buscar_internet_fn
        self.client = client
        self.modelo = modelo
    
    async def obtener_serie_precios(self, ticker: str) -> List[float]:
        """
        Intenta obtener serie histórica de precios del ticker.
        """
        precios_yahoo = await asyncio.to_thread(self._obtener_serie_precios_yahoo, ticker)
        if len(precios_yahoo) >= 14:
            return precios_yahoo

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        query = f"{ticker} historical prices last 12 months data {fecha_hoy}"
        
        try:
            resultado = await asyncio.to_thread(self.buscar, query)
            
            # Usar IA para extraer precios
            prompt = f"""Extrae una serie de precios históricos de esta información sobre {ticker}.

INFORMACIÓN:
{resultado[:2000]}

Responde SOLO una lista de números (precios) separados por comas, del más antiguo al más reciente.
Ejemplo: 45.2, 46.1, 44.8, 47.3, 48.1, 49.5

Si no encuentras precios históricos, responde: NO_DISPONIBLE
"""
            
            response = await asyncio.to_thread(
                self.client.chat.complete,
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            texto = response.choices[0].message.content.strip()
            
            if "NO_DISPONIBLE" in texto:
                return []
            
            # Parsear precios (robusto ante markdown/listas/formatos mixtos)
            candidatos = re.findall(r"\d+(?:\.\d+)?", texto.replace(',', '.'))
            precios = [float(p) for p in candidatos]
            
            return precios if len(precios) >= 5 else []
        
        except Exception as e:
            logging.error(f"Error obteniendo precios históricos: {e}")
            return []
    
    async def obtener_metricas_fundamentales(self, ticker: str, nombre: str) -> Dict:
        """
        Busca métricas fundamentales en múltiples fuentes.
        """
        metricas_yahoo = await asyncio.to_thread(self._obtener_metricas_fundamentales_yahoo, ticker)
        if metricas_yahoo:
            return metricas_yahoo

        fecha_hoy = datetime.now().strftime("%d %B %Y")
        
        # Búsquedas específicas
        queries = {
            'valoracion': f"{ticker} {nombre} PER price earnings ratio PEG {fecha_hoy}",
            'rentabilidad': f"{ticker} ROE return on equity ROA profit margins",
            'deuda': f"{ticker} debt to equity ratio balance sheet financial health",
            'crecimiento': f"{ticker} revenue growth earnings growth YoY",
            'cash_flow': f"{ticker} free cash flow FCF operating cash flow",
            'dividendo': f"{ticker} dividend yield payout ratio dividend growth"
        }
        
        contexto = ""
        for categoria, query in queries.items():
            try:
                resultado = await asyncio.to_thread(self.buscar, query)
                contexto += f"\n=== {categoria.upper()} ===\n{resultado}\n"
            except Exception as e:
                logging.error(f"Error en búsqueda {categoria}: {e}")
                continue
        
        # Extraer métricas con IA
        prompt = f"""Analiza esta información sobre {ticker} y extrae las métricas fundamentales.

INFORMACIÓN RECOPILADA:
{contexto[:3000]}

Responde en formato JSON con estas métricas (usa null si no está disponible):
{{
  "per": valor_numerico,
  "peg": valor_numerico,
  "roe": valor_porcentaje,
  "deuda_patrimonio": valor_ratio,
  "margen_operativo": valor_porcentaje,
  "crecimiento_ingresos": valor_porcentaje,
  "fcf": "positivo|negativo|null",
  "dividend_yield": valor_porcentaje,
  "per_sector": valor_numerico_promedio_sector,
  "valoracion": "infravalorada|justa|sobrevalorada"
}}

Sé conservador. Si no estás seguro, usa null.
"""
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.complete,
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            import json
            metricas = json.loads(response.choices[0].message.content)
            return metricas
        
        except Exception as e:
            logging.error(f"Error extrayendo métricas: {e}")
            return {}

    def _obtener_variantes_ticker(self, ticker: str) -> List[str]:
        """Devuelve variantes para mejorar la resolución del ticker."""
        base = (ticker or "").strip().upper()
        if not base:
            return []

        variantes = [base]
        if '.' not in base:
            variantes.append(f"{base}.MC")
        return variantes

    def _obtener_serie_precios_yahoo(self, ticker: str) -> List[float]:
        """Obtiene precios desde Yahoo Finance chart API pública."""
        headers = {'User-Agent': 'Mozilla/5.0'}

        for tk in self._obtener_variantes_ticker(ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}?range=6mo&interval=1d"
                resp = requests.get(url, timeout=8, headers=headers)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                result = ((data.get('chart') or {}).get('result') or [{}])[0]
                closes = (((result.get('indicators') or {}).get('quote') or [{}])[0].get('close') or [])
                precios = [float(c) for c in closes if c is not None and c > 0]

                if len(precios) >= 14:
                    return precios
            except Exception:
                continue

        return []

    def _obtener_metricas_fundamentales_yahoo(self, ticker: str) -> Dict:
        """Obtiene fundamentales clave desde Yahoo Finance quoteSummary."""
        headers = {'User-Agent': 'Mozilla/5.0'}
        modules = "defaultKeyStatistics,financialData,summaryDetail"

        for tk in self._obtener_variantes_ticker(ticker):
            try:
                url = (
                    f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{tk}"
                    f"?modules={modules}"
                )
                resp = requests.get(url, timeout=8, headers=headers)
                if resp.status_code != 200:
                    continue

                payload = resp.json()
                result = ((payload.get('quoteSummary') or {}).get('result') or [{}])[0]
                dks = result.get('defaultKeyStatistics') or {}
                fd = result.get('financialData') or {}
                sd = result.get('summaryDetail') or {}

                def _raw(obj, key):
                    val = (obj.get(key) or {})
                    return val.get('raw') if isinstance(val, dict) else val

                per = _raw(sd, 'trailingPE')
                peg = _raw(dks, 'pegRatio')
                roe = _raw(fd, 'returnOnEquity')
                deuda = _raw(fd, 'debtToEquity')
                margen = _raw(fd, 'operatingMargins')
                crecimiento = _raw(fd, 'revenueGrowth')
                fcf = _raw(fd, 'freeCashflow')
                div_yield = _raw(sd, 'dividendYield')

                metricas = {
                    'per': round(per, 2) if isinstance(per, (int, float)) else None,
                    'peg': round(peg, 2) if isinstance(peg, (int, float)) else None,
                    'roe': round(roe * 100, 2) if isinstance(roe, (int, float)) else None,
                    'deuda_patrimonio': round(deuda / 100, 2) if isinstance(deuda, (int, float)) else None,
                    'margen_operativo': round(margen * 100, 2) if isinstance(margen, (int, float)) else None,
                    'crecimiento_ingresos': round(crecimiento * 100, 2) if isinstance(crecimiento, (int, float)) else None,
                    'fcf': 'positivo' if isinstance(fcf, (int, float)) and fcf > 0 else ('negativo' if isinstance(fcf, (int, float)) else None),
                    'dividend_yield': round(div_yield * 100, 2) if isinstance(div_yield, (int, float)) else None,
                    'per_sector': None,
                    'valoracion': 'justa'
                }

                datos_disponibles = sum(
                    1 for clave in ['per', 'peg', 'roe', 'deuda_patrimonio', 'margen_operativo', 'crecimiento_ingresos']
                    if metricas.get(clave) is not None
                )
                if datos_disponibles >= 2:
                    return metricas
            except Exception:
                continue

        return {}
    
    async def obtener_consenso_analistas(self, ticker: str, nombre: str) -> Dict:
        """
        Busca consenso de analistas profesionales.
        """
        fecha_hoy = datetime.now().strftime("%B %Y")
        
        queries = [
            f"{ticker} {nombre} analyst consensus recommendation {fecha_hoy}",
            f"{ticker} price target analyst estimates {fecha_hoy}",
            f"{ticker} buy sell hold ratings analyst {fecha_hoy}"
        ]
        
        contexto = ""
        for query in queries:
            try:
                resultado = await asyncio.to_thread(self.buscar, query)
                contexto += f"\n{resultado}\n"
            except:
                continue
        
        # Extraer consenso con IA
        prompt = f"""Extrae el consenso de analistas sobre {ticker}.

INFORMACIÓN:
{contexto[:2500]}

Responde en JSON:
{{
  "recomendacion": "Strong Buy|Buy|Hold|Sell|Strong Sell",
  "num_analistas": numero_total,
  "precio_objetivo_medio": valor,
  "precio_objetivo_alto": valor,
  "precio_objetivo_bajo": valor,
  "comprar": numero,
  "mantener": numero,
  "vender": numero
}}

Si no hay datos, usa null.
"""
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.complete,
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            import json
            consenso = json.loads(response.choices[0].message.content)
            return consenso
        
        except Exception as e:
            logging.error(f"Error obteniendo consenso: {e}")
            return {}
    
    async def analizar_sentimiento_noticias(self, ticker: str, nombre: str) -> Dict:
        """
        Analiza sentimiento de noticias recientes.
        """
        query = f"{ticker} {nombre} news última semana important developments"
        
        try:
            noticias = await asyncio.to_thread(self.buscar, query)
            
            prompt = f"""Analiza el sentimiento de estas noticias recientes sobre {ticker}.

NOTICIAS:
{noticias[:2000]}

Responde en JSON:
{{
  "sentimiento": "Muy Positivo|Positivo|Neutral|Negativo|Muy Negativo",
  "score": valor_de_-1_a_1,
  "catalizadores_positivos": ["Cat 1", "Cat 2"],
  "riesgos": ["Riesgo 1", "Riesgo 2"],
  "eventos_proximos": ["Evento 1"]
}}
"""
            
            response = await asyncio.to_thread(
                self.client.chat.complete,
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            import json
            sentimiento = json.loads(response.choices[0].message.content)
            return sentimiento
        
        except Exception as e:
            logging.error(f"Error analizando sentimiento: {e}")
            return {'sentimiento': 'Neutral', 'score': 0}
