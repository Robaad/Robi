"""
CONTENT ENGINE - Motor de Generación de Contenido Especializado
================================================================
Este módulo gestiona la generación de contenido complejo usando:
- Templates especializados por tipo de tarea
- Validación automática de resultados
- Refinamiento iterativo
- Control de calidad
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import re
import json

class ContentEngine:
    """Motor de generación de contenido con templates especializados."""
    
    def __init__(
        self,
        client,
        modelo_avanzado="mistral-large-latest",
        perfil_redactor="académico",
        tono="formal",
    ):
        self.client = client
        self.modelo = modelo_avanzado
        self.perfil_redactor = perfil_redactor
        self.tono = tono
        
    # async def generar_estudio_academico(
    #     self, 
    #     tema: str, 
    #     tipo: str = "general",
    #     nivel: str = "universitario",
    #     extension: str = "completo"
    # ) -> Dict[str, any]:
    #     """
    #     Genera un estudio estructurado.
        
    #     Args:
    #         tema: Tema del estudio
    #         tipo: general|programacion_didactica|tfg|investigacion
    #         nivel: secundaria|fp|universitario|master
    #         extension: breve|medio|completo|extenso
        
    #     Returns:
    #         Dict con 'indice', 'secciones' y 'metadata'
    #     """
        
    #     # 1. Generar estructura inteligente
    #     estructura = await self._generar_estructura(tema, tipo, nivel, extension)
        
    #     # 2. Desarrollar cada sección con contexto
    #     secciones_desarrolladas = []
    #     for i, seccion in enumerate(estructura['secciones'], 1):
    #         # Sistema de reintentos para manejar rate limits
    #         max_intentos = 3
    #         contenido = None
            
    #         for intento in range(max_intentos):
    #             try:
    #                 contenido = await self._desarrollar_seccion(
    #                     seccion=seccion,
    #                     tema_global=tema,
    #                     contexto_previo=secciones_desarrolladas,
    #                     numero=i,
    #                     total=len(estructura['secciones'])
    #                 )

    #                 break  # Éxito, salir del bucle de reintentos
                    
    #             except Exception as e:
    #                 if "429" in str(e) or "rate_limit" in str(e).lower():
    #                     if intento < max_intentos - 1:
    #                         import asyncio
    #                         espera = 10 * (intento + 1)  # Backoff exponencial: 10s, 20s, 30s
    #                         logging.warning(f"Rate limit alcanzado. Reintentando en {espera}s...")
    #                         await asyncio.sleep(espera)
    #                     else:
    #                         raise Exception(f"Rate limit persistente después de {max_intentos} intentos")
    #                 else:
    #                     raise e  # Error diferente, propagar
            
    #         if contenido is None:
    #             raise Exception(f"No se pudo generar contenido para sección {i}")
            
    #         # Validar y refinar si es necesario
    #         if await self._necesita_refinamiento(contenido):
    #             # También con reintentos para el refinamiento
    #             for intento in range(2):
    #                 try:
    #                     contenido = await self._refinar_contenido(contenido, seccion)
    #                     break
    #                 except Exception as e:
    #                     if "429" in str(e) and intento == 0:
    #                         import asyncio
    #                         await asyncio.sleep(10)
    #                     else:
    #                         # Si falla el refinamiento, usar contenido original
    #                         logging.warning(f"No se pudo refinar sección {i}, usando original")
    #                         break
            
    #         secciones_desarrolladas.append({
    #             'titulo': seccion,
    #             'contenido': contenido,
    #             'numero': i
    #         })
        
    #     return {
    #         'indice': estructura['secciones'],
    #         'secciones': secciones_desarrolladas,
    #         'metadata': {
    #             'tema': tema,
    #             'tipo': tipo,
    #             'nivel': nivel,
    #             'fecha_generacion': datetime.now().isoformat(),
    #             'modelo': self.modelo
    #         }
    #     }
    
    async def generar_estudio_academico(
        self, 
        tema: str, 
        tipo: str = "general",
        nivel: str = "universitario",
        extension: str = "completo"
    ) -> Dict[str, any]:
        
        # 1. Generar estructura inteligente
        estructura = await self._generar_estructura(tema, tipo, nivel, extension)
        
        # 2. Desarrollar cada sección con contexto
        secciones_desarrolladas = []
        for i, seccion in enumerate(estructura['secciones'], 1):
            max_intentos = 3
            contenido_raw = None # Usamos _raw para guardar el texto con etiquetas JSON
            
            for intento in range(max_intentos):
                try:
                    # Llamada original a la IA
                    contenido_raw = await self._desarrollar_seccion(
                        seccion=seccion,
                        tema_global=tema,
                        contexto_previo=secciones_desarrolladas,
                        numero=i,
                        total=len(estructura['secciones']),
                        extension=extension
                    )
                    break 
                    
                except Exception as e:
                    if "429" in str(e) or "rate_limit" in str(e).lower():
                        if intento < max_intentos - 1:
                            import asyncio
                            espera = 10 * (intento + 1)
                            logging.warning(f"Rate limit alcanzado. Reintentando en {espera}s...")
                            await asyncio.sleep(espera)
                        else:
                            raise Exception(f"Rate limit persistente después de {max_intentos} intentos")
                    else:
                        raise e

            if contenido_raw is None:
                raise Exception(f"No se pudo generar contenido para sección {i}")

            # --- NUEVA LÓGICA DE GRÁFICOS ---
            # Extraemos los datos del gráfico antes de limpiar el texto
            datos_v = self._extraer_datos_visuales(contenido_raw)
            
            # Limpiamos el texto (quitar etiquetas, asteriscos, etc.)
            contenido_final = self._limpiar_formato(contenido_raw)
            # -------------------------------

            # Validar y refinar si es necesario
            if await self._necesita_refinamiento(contenido_final, extension):
                for intento in range(2):
                    try:
                        # Al refinar, pedimos que mantenga la sustancia pero mejore el texto
                        contenido_final = await self._refinar_contenido(contenido_final, seccion)
                        break
                    except Exception as e:
                        if "429" in str(e) and intento == 0:
                            import asyncio
                            await asyncio.sleep(10)
                        else:
                            logging.warning(f"No se pudo refinar sección {i}, usando original")
                            break
            
            # Guardamos la sección con el campo extra 'datos_visuales'
            secciones_desarrolladas.append({
                'titulo': seccion,
                'contenido': contenido_final,
                'numero': i,
                'datos_visuales': datos_v  # <--- AQUÍ SE GUARDA EL GRÁFICO
            })
        
        return {
            'indice': estructura['secciones'],
            'secciones': secciones_desarrolladas,
            'metadata': {
                'tema': tema,
                'tipo': tipo,
                'nivel': nivel,
                'fecha_generacion': datetime.now().isoformat(),
                'modelo': self.modelo
            }
        }


    async def _generar_estructura(self, tema: str, tipo: str, nivel: str, extension: str) -> Dict:
        """Genera estructura optimizada según el tipo de contenido."""
        
        # Templates especializados
        templates = {
            'programacion_didactica': self._template_programacion_didactica,
            'investigacion': self._template_investigacion,
            'tfg': self._template_tfg,
            'general': self._template_general
        }
        
        template = templates.get(tipo, self._template_general)
        prompt = template(tema, nivel, extension)
        
        response = await asyncio.to_thread(
            self.client.chat.complete,
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3  # Baja para estructura consistente
        )
        
        # Parsear respuesta
        texto_respuesta = response.choices[0].message.content
        secciones = self._extraer_secciones(texto_respuesta)
        
        return {
            'secciones': secciones,
            'prompt_usado': prompt
        }
    
    async def _desarrollar_seccion(
        self, 
        seccion: str, 
        tema_global: str, 
        contexto_previo: List[Dict],
        numero: int,
        total: int,
        extension: str = "completo"
    ) -> str:
        """Desarrolla una sección con contexto completo."""
        
        # Construir contexto de lo ya escrito
        resumen_previo = ""
        if contexto_previo:
            ultimas_secciones = contexto_previo[-2:]  # Últimas 2 secciones para coherencia
            resumen_previo = "\n\nCONTEXTO YA ESCRITO:\n"
            for sec in ultimas_secciones:
                resumen_previo += f"\n{sec['titulo']}: {sec['contenido'][:200]}...\n"
        
        min_palabras, max_palabras = self._resolver_rango_palabras(extension)

        prompt = f"""Eres un experto redactor {self.perfil_redactor}.

TAREA: Desarrollar la sección {numero} de {total} de un estudio sobre "{tema_global}"

SECCIÓN A DESARROLLAR: {seccion}
{resumen_previo}

REQUISITOS ESPECIALES DE VISUALIZACIÓN:
Si la sección contiene datos numéricos, comparativas o jerarquías, DEBES incluir al final del texto un bloque de datos JSON con el siguiente formato:

[GRAFICO_DATA]
{{
  "tipo": "barras" | "tarta" | "lineas" | "organigrama",
  "titulo": "Título descriptivo del gráfico",
  "datos": {{"Etiqueta1": valor1, "Etiqueta2": valor2}} o {{"NodoPadre": ["Hijo1", "Hijo2"]}} para organigramas
}}
[/GRAFICO_DATA]

REQUISITOS:
1. Contenido denso, profesional y específico
2. Mínimo {min_palabras} palabras, máximo {max_palabras}
3. Datos concretos, no generalidades
4. Coherencia con lo ya escrito
5. Citas y referencias obligatorias
6. Lenguaje {self.tono} pero comprensible

IMPORTANTE:
- NO repitas información de secciones anteriores
- NO uses frases genéricas como "es importante destacar"
- SÍ aporta información concreta y útil
- SÍ usa ejemplos reales cuando sea posible

FORMATO DE SALIDA:
Texto directo sin markdown ni asteriscos. Solo párrafos bien estructurados y se deben citar todas las fuentes de los datos que se utilicen.
"""
        
        response = await asyncio.to_thread(
            self.client.chat.complete,
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5  # Media para balance creatividad/precisión
        )
        
        contenido = response.choices[0].message.content
        
        # Limpiar formato
        contenido = self._limpiar_formato(contenido)
        
        return contenido

    def _resolver_rango_palabras(self, extension: str) -> tuple[int, int]:
        return {
            "breve": (180, 320),
            "medio": (300, 520),
            "completo": (400, 800),
            "extenso": (700, 1100),
        }.get(extension, (400, 800))
    
    async def _necesita_refinamiento(self, contenido: str, extension: str = "completo") -> bool:
        """Detecta si el contenido es demasiado genérico o vacío."""
        
        # Indicadores de contenido pobre
        palabras_vacias = ['importante', 'fundamental', 'esencial', 'clave', 'relevante']
        frases_genericas = [
            'es importante destacar',
            'cabe mencionar',
            'es fundamental',
            'no podemos olvidar',
            'en este contexto'
        ]
        
        # Contadores
        palabras = len(contenido.split())
        cuenta_vacias = sum(1 for p in palabras_vacias if p in contenido.lower())
        cuenta_genericas = sum(1 for f in frases_genericas if f in contenido.lower())
        min_palabras, _ = self._resolver_rango_palabras(extension)
        umbral_palabras = max(150, int(min_palabras * 0.8))
        
        # Criterios de refinamiento
        if palabras < umbral_palabras:
            return True  # Demasiado corto
        if cuenta_vacias > 10:
            return True  # Demasiadas palabras vacías
        if cuenta_genericas > 3:
            return True  # Demasiadas frases genéricas
        
        return False
    
    async def _refinar_contenido(self, contenido: str, seccion: str) -> str:
        """Refina contenido genérico o vacío."""
        
        prompt = f"""Este contenido sobre "{seccion}" es demasiado genérico:

{contenido}

TAREA: Reescríbelo haciendo lo siguiente:
1. Sustituye generalidades por datos concretos
2. Añade ejemplos específicos
3. Elimina frases de relleno
4. Duplica la profundidad técnica
5. Mantén extensión similar pero con más sustancia

Responde solo con el texto mejorado, sin comentarios.
"""
        
        response = await asyncio.to_thread(
            self.client.chat.complete,
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        
        return self._limpiar_formato(response.choices[0].message.content)
    
    def _limpiar_formato(self, texto: str) -> str:
        """Limpia markdown y formato innecesario."""
        texto = texto.replace('###', '').replace('##', '').replace('#', '')
        texto = texto.replace('**', '').replace('*', '')
        texto = texto.replace('```', '')
        texto = re.sub(r'\n{3,}', '\n\n', texto)  # Max 2 saltos de línea
        return texto.strip()
    
    def _extraer_secciones(self, texto: str) -> List[str]:
        """Extrae títulos de secciones del texto."""
        lineas = texto.split('\n')
        secciones = []
        
        for linea in lineas:
            # Buscar líneas que parezcan títulos
            linea = linea.strip()
            if not linea:
                continue
            
            # Patrones de título
            if re.match(r'^\d+\.', linea):  # Empieza con número
                secciones.append(re.sub(r'^\d+\.\s*', '', linea))
            elif re.match(r'^[IVX]+\.', linea):  # Numeración romana
                secciones.append(re.sub(r'^[IVX]+\.\s*', '', linea))
            elif len(linea) > 10 and len(linea) < 100 and not linea.endswith('.'):
                # Línea corta sin punto final (probable título)
                secciones.append(linea)
        
        # Limpiar duplicados manteniendo orden
        secciones_limpias = []
        for s in secciones:
            s_limpio = self._limpiar_formato(s)
            if s_limpio and s_limpio not in secciones_limpias:
                secciones_limpias.append(s_limpio)
        
        return secciones_limpias[:15]  # Max 15 secciones
    
    # ============ TEMPLATES ESPECIALIZADOS ============
    
    def _template_programacion_didactica(self, tema: str, nivel: str, extension: str) -> str:
        """Template para programaciones didácticas de FP."""
        max_secciones = {
            "breve": 8,
            "medio": 10,
            "completo": 12,
            "extenso": 14,
        }.get(extension, 12)
        return f"""Genera un ÍNDICE para una programación didáctica de {tema} en {nivel}.

Debe incluir obligatoriamente (formato LOMLOE):
1. Introducción y contextualización
2. Objetivos generales del módulo
3. Competencias profesionales, personales y sociales
4. Resultados de aprendizaje y criterios de evaluación
5. Contenidos (conceptuales, procedimentales, actitudinales)
6. Secuenciación y temporalización por unidades didácticas
7. Metodología didáctica
8. Evaluación (criterios, instrumentos, recuperación)
9. Atención a la diversidad
10. Recursos didácticos y materiales
11. Actividades complementarias y extraescolares

Responde SOLO con el listado numerado de secciones, sin explicaciones.
Si la extensión es breve, fusiona apartados para no superar {max_secciones} secciones.
Máximo {max_secciones} secciones principales.
"""
    
    def _template_investigacion(self, tema: str, nivel: str, extension: str) -> str:
        """Template para estudios de investigación."""
        max_secciones = {
            "breve": 6,
            "medio": 8,
            "completo": 10,
            "extenso": 12,
        }.get(extension, 10)
        return f"""Genera un ÍNDICE para un estudio de investigación sobre: {tema}

Nivel académico: {nivel}

Estructura típica de investigación científica:
1. Resumen/Abstract
2. Introducción y justificación
3. Estado del arte / Revisión bibliográfica
4. Marco teórico
5. Hipótesis y objetivos
6. Metodología
7. Resultados
8. Discusión
9. Conclusiones
10. Limitaciones y futuras líneas
11. Referencias bibliográficas

Responde SOLO con el listado numerado adaptado a este tema específico.
Máximo {max_secciones} secciones.
"""
    
    def _template_tfg(self, tema: str, nivel: str, extension: str) -> str:
        """Template para Trabajos Fin de Grado/Máster."""
        max_secciones = {
            "breve": 6,
            "medio": 7,
            "completo": 8,
            "extenso": 10,
        }.get(extension, 8)
        return f"""Genera un ÍNDICE para un TFG/TFM sobre: {tema}

Nivel: {nivel}

Estructura recomendada:
1. Introducción (contexto, motivación, objetivos)
2. Estado del arte
3. Marco teórico/conceptual
4. Diseño/metodología/desarrollo
5. Resultados/implementación
6. Análisis y discusión
7. Conclusiones y trabajo futuro
8. Bibliografía
9. Anexos (si procede)

Responde SOLO con el listado numerado específico para este tema.
Máximo {max_secciones} secciones principales.
"""
    
    def _template_general(self, tema: str, nivel: str, extension: str) -> str:
        """Template genérico adaptable."""
        num_secciones = {
            'breve': 4,
            'medio': 8,
            'completo': 10,
            'extenso': 12
        }.get(extension, 8)
        
        return f"""Genera un ÍNDICE estructurado para un estudio sobre: {tema}

Nivel: {nivel}
Extensión deseada: {extension}

Genera entre {num_secciones-2} y {num_secciones} secciones principales.

REQUISITOS:
- Cada sección debe ser específica al tema (nada genérico)
- Orden lógico y progresivo
- Balance entre teoría y práctica
- Incluir ejemplos/casos prácticos si es pertinente

Responde SOLO con el listado numerado de títulos de sección.
Sin introducciones ni explicaciones.
"""

    def _extraer_datos_visuales(self, texto: str):
        try:
            # Buscamos el bloque [GRAFICO_DATA]
            match = re.search(r"\[GRAFICO_DATA\]\s*(\{.*?\})\s*\[/GRAFICO_DATA\]", texto, re.DOTALL)
            if match:
                import json
                # Limpiamos posibles espacios o saltos de línea raros
                json_str = match.group(1).strip()
                return json.loads(json_str)
        except Exception as e:
            logging.error(f"Error parseando JSON: {e}")
        return None

    def _limpiar_formato(self, texto: str) -> str:
        """Limpia las etiquetas de gráficos y otros formatos del texto final."""
        # Eliminamos todo el bloque [GRAFICO_DATA]...[/GRAFICO_DATA]
        texto_limpio = re.sub(r"\[GRAFICO_DATA\].*?\[/GRAFICO_DATA\]", "", texto, flags=re.DOTALL)
        # Opcional: limpiar asteriscos excesivos de negritas si lo prefieres
        return texto_limpio.strip()

class AnalisisFinanciero:
    """Motor especializado para análisis financiero profundo."""
    
    def __init__(self, client, buscar_internet_func, modelo="mistral-large-latest"):
        self.client = client
        self.buscar = buscar_internet_func
        self.modelo = modelo
    
    async def analisis_completo_valor(self, ticker: str) -> Dict[str, str]:
        """
        Análisis 360° de un valor con múltiples fuentes.
        
        Returns:
            Dict con secciones: tesis, fundamentales, técnico, riesgos, valoracion
        """
        
        hoy = datetime.now().strftime("%d de %B de %Y")
        
        # 1. Recopilar datos de múltiples fuentes
        queries = [
            f"precio acción {ticker} tiempo real {hoy}",
            f"análisis fundamental {ticker} resultados trimestrales PER deuda",
            f"precio objetivo {ticker} consenso analistas bancos 2026",
            f"noticias {ticker} última semana",
            f"análisis técnico {ticker} soportes resistencias"
        ]
        
        datos_recopilados = {}
        for query in queries:
            categoria = query.split()[0]  # Primera palabra como clave
            datos_recopilados[categoria] = self.buscar(query)
        
        # 2. Generar cada sección del análisis
        secciones = {}
        
        # Tesis de inversión
        secciones['tesis'] = await self._generar_tesis(ticker, datos_recopilados)
        
        # Fundamentales
        secciones['fundamentales'] = await self._analisis_fundamental(ticker, datos_recopilados)
        
        # Riesgos (Bear Case)
        secciones['riesgos'] = await self._analisis_riesgos(ticker, datos_recopilados)
        
        # Valoración
        secciones['valoracion'] = await self._valoracion_precio(ticker, datos_recopilados)
        
        # Recomendación final
        secciones['recomendacion'] = await self._recomendacion_final(ticker, secciones)
        
        return secciones
    
    async def _generar_tesis(self, ticker: str, datos: Dict) -> str:
        """Genera la tesis de inversión."""
        prompt = f"""Como analista senior, resume la tesis de inversión de {ticker}.

Datos disponibles:
{datos.get('precio', 'No disponible')}
{datos.get('noticias', 'No disponible')}

Responde en 3-4 párrafos:
1. Situación actual del negocio
2. Catalizadores principales
3. Posicionamiento competitivo

Sé específico, usa datos concretos. Sin introducciones genéricas.
"""
        
        response = self.client.chat.complete(
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    async def _analisis_fundamental(self, ticker: str, datos: Dict) -> str:
        """Análisis de fundamentales."""
        prompt = f"""Analiza los fundamentales de {ticker}.

Datos:
{datos.get('análisis', 'No disponible')}

Cubre:
- Métricas clave (PER, P/B, ROE, deuda/EBITDA)
- Tendencia de ingresos y márgenes
- Salud financiera
- Comparación con competencia

Datos concretos, sin relleno.
"""
        
        response = self.client.chat.complete(
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        return response.choices[0].message.content
    
    async def _analisis_riesgos(self, ticker: str, datos: Dict) -> str:
        """Análisis de riesgos (Bear Case)."""
        prompt = f"""Como analista ESCÉPTICO, identifica los mayores riesgos de {ticker}.

Datos:
{datos.get('noticias', 'No disponible')}

Identifica 3-4 riesgos REALES que podrían hacer caer el valor 20%+:
- Riesgos de negocio
- Riesgos financieros
- Riesgos de mercado/sector
- Riesgos regulatorios

Sé crítico y específico. Nada de "la competencia podría aumentar".
"""
        
        response = self.client.chat.complete(
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        
        return response.choices[0].message.content
    
    async def _valoracion_precio(self, ticker: str, datos: Dict) -> str:
        """Valoración y precio objetivo."""
        prompt = f"""Calcula la valoración de {ticker}.

Datos:
{datos.get('precio', 'No disponible')}

Responde:
1. Precio actual vs precio objetivo consenso
2. Upside/downside potencial (%)
3. Rango de precios objetivo (mínimo-máximo)
4. Valoración: sobrevalorado/infravalorado/justo

Solo números y conclusiones, sin explicaciones largas.
"""
        
        response = self.client.chat.complete(
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        return response.choices[0].message.content
    
    async def _recomendacion_final(self, ticker: str, secciones: Dict) -> str:
        """Genera recomendación final basada en todo el análisis."""
        
        resumen_analisis = f"""
Tesis: {secciones['tesis'][:200]}
Fundamentales: {secciones['fundamentales'][:200]}
Riesgos: {secciones['riesgos'][:200]}
Valoración: {secciones['valoracion'][:200]}
"""
        
        prompt = f"""Basándote en este análisis de {ticker}:

{resumen_analisis}

Da una recomendación clara:
- COMPRAR / MANTENER / VENDER
- Precio de entrada ideal
- Horizonte temporal
- Nivel de riesgo (Bajo/Medio/Alto)
- Stop loss sugerido

Formato: directo, sin rodeos, como si fuera para un cliente.
"""
        
        response = self.client.chat.complete(
            model=self.modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        return response.choices[0].message.content
