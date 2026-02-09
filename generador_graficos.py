"""
GENERADOR DE GRÁFICOS - Extracción de datos y visualización automática
======================================================================
Este módulo analiza texto académico, extrae datos numéricos y genera
gráficos profesionales para insertar en documentos Word.
"""

import re
import logging
import asyncio
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI para servidores
from io import BytesIO
from typing import Dict, List, Optional, Tuple
import numpy as np

# Configuración de estilo profesional
plt.style.use('seaborn-v0_8-darkgrid')
COLORES_PROFESIONALES = ['#2E86C1', '#E74C3C', '#27AE60', '#F39C12', '#8E44AD', '#16A085']


class ExtractorDatos:
    """Extrae datos estructurados de texto académico."""
    
    def __init__(self, client, modelo="mistral-large-latest"):
        self.client = client
        self.modelo = modelo
    
    async def detectar_y_extraer_datos(self, contenido: str, titulo_seccion: str) -> Optional[Dict]:
        """
        Detecta si una sección contiene datos visualizables y los extrae.
        
        Returns:
            Dict con 'tipo', 'titulo', 'datos' si encuentra datos
            None si no hay datos visualizables
        """
        
        # Detectar si el contenido tiene datos numéricos relevantes
        indicadores_datos = [
            r'\d+%',  # Porcentajes
            r'\d+\.\d+',  # Decimales
            r'\d{1,3}(,\d{3})*',  # Números con separadores de miles
            'estadística', 'porcentaje', 'distribución', 'comparación',
            'tabla', 'datos', 'cifras', 'número', 'cantidad'
        ]
        
        tiene_datos = any(
            re.search(patron, contenido, re.IGNORECASE) 
            for patron in indicadores_datos
        )
        
        if not tiene_datos:
            return None
        
        # Usar IA para extraer datos estructurados
        prompt = f"""Analiza este texto de la sección "{titulo_seccion}" y extrae SOLO datos numéricos visualizables.

TEXTO:
{contenido[:1500]}

REGLAS:
1. Si encuentras datos numéricos comparables (porcentajes, cantidades, distribuciones), extráelos
2. Responde SOLO en formato JSON
3. Si NO hay datos visualizables, responde: {{"tiene_datos": false}}
4. Si hay datos, responde:
   {{
     "tiene_datos": true,
     "tipo_grafico": "barras|lineas|tarta|puntos",
     "titulo": "Título descriptivo del gráfico",
     "eje_x": "Nombre del eje X",
     "eje_y": "Nombre del eje Y",
     "datos": {{
       "Categoría 1": valor_numerico,
       "Categoría 2": valor_numerico,
       ...
     }}
   }}

EJEMPLOS:

Texto: "El 45% prefiere Python, 30% Java y 25% JavaScript"
Respuesta: {{"tiene_datos": true, "tipo_grafico": "tarta", "titulo": "Preferencias de lenguajes", "datos": {{"Python": 45, "Java": 30, "JavaScript": 25}}}}

Texto: "La adopción de IA creció del 20% en 2020 al 65% en 2024"
Respuesta: {{"tiene_datos": true, "tipo_grafico": "lineas", "titulo": "Crecimiento adopción IA", "eje_x": "Año", "eje_y": "Porcentaje", "datos": {{"2020": 20, "2021": 30, "2022": 42, "2023": 55, "2024": 65}}}}

Responde SOLO el JSON, sin explicaciones.
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
            resultado = json.loads(response.choices[0].message.content)
            
            if not resultado.get('tiene_datos', False):
                return None
            
            return {
                'tipo': resultado['tipo_grafico'],
                'titulo': resultado['titulo'],
                'eje_x': resultado.get('eje_x', ''),
                'eje_y': resultado.get('eje_y', 'Valor'),
                'datos': resultado['datos']
            }
        
        except Exception as e:
            logging.error(f"Error extrayendo datos: {e}")
            return None


class GeneradorGraficos:
    """Genera gráficos profesionales con matplotlib."""
    
    @staticmethod
    def generar_grafico(datos_visual: Dict) -> BytesIO:
        """
        Genera un gráfico y lo devuelve como imagen en memoria.
        
        Args:
            datos_visual: Dict con 'tipo', 'titulo', 'datos', 'eje_x', 'eje_y'
        
        Returns:
            BytesIO con la imagen PNG
        """
        tipo = datos_visual['tipo']
        titulo = datos_visual['titulo']
        datos = datos_visual['datos']
        
        # Preparar datos
        etiquetas = list(datos.keys())
        valores = [float(v) for v in datos.values()]
        
        # Crear figura
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if tipo == 'barras':
            barras = ax.bar(etiquetas, valores, color=COLORES_PROFESIONALES[:len(etiquetas)])
            
            # Añadir valores sobre las barras
            for barra in barras:
                altura = barra.get_height()
                ax.text(barra.get_x() + barra.get_width()/2., altura,
                       f'{altura:.1f}',
                       ha='center', va='bottom', fontweight='bold')
            
            ax.set_ylabel(datos_visual.get('eje_y', 'Valor'))
            if datos_visual.get('eje_x'):
                ax.set_xlabel(datos_visual['eje_x'])
            plt.xticks(rotation=45, ha='right')
        
        elif tipo == 'lineas':
            ax.plot(etiquetas, valores, marker='o', linewidth=2.5, 
                   markersize=8, color=COLORES_PROFESIONALES[0])
            
            # Añadir valores en los puntos
            for i, (x, y) in enumerate(zip(etiquetas, valores)):
                ax.text(i, y, f'{y:.1f}', ha='center', va='bottom', fontweight='bold')
            
            ax.set_ylabel(datos_visual.get('eje_y', 'Valor'))
            if datos_visual.get('eje_x'):
                ax.set_xlabel(datos_visual['eje_x'])
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
        
        elif tipo == 'tarta':
            # Crear gráfico de tarta
            colores = COLORES_PROFESIONALES[:len(etiquetas)]
            wedges, texts, autotexts = ax.pie(valores, labels=etiquetas, autopct='%1.1f%%',
                                              colors=colores, startangle=90)
            
            # Mejorar legibilidad
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(10)
            
            for text in texts:
                text.set_fontsize(11)
            
            ax.axis('equal')
        
        elif tipo == 'puntos':
            ax.scatter(range(len(valores)), valores, s=100, 
                      color=COLORES_PROFESIONALES[0], alpha=0.6, edgecolors='black')
            
            ax.set_ylabel(datos_visual.get('eje_y', 'Valor'))
            if datos_visual.get('eje_x'):
                ax.set_xlabel(datos_visual['eje_x'])
            ax.set_xticks(range(len(etiquetas)))
            ax.set_xticklabels(etiquetas, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
        
        # Título del gráfico
        plt.title(titulo, fontsize=14, fontweight='bold', pad=20)
        
        # Ajustar layout
        plt.tight_layout()
        
        # Guardar en memoria
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        buffer.seek(0)
        return buffer


class IntegradorGraficosWord:
    """Integra gráficos en documentos Word."""
    
    def __init__(self, client, modelo="mistral-large-latest"):
        self.extractor = ExtractorDatos(client, modelo)
        self.generador = GeneradorGraficos()
    
    async def procesar_seccion_con_graficos(
        self, 
        titulo_seccion: str, 
        contenido: str, 
        doc,
        numero_seccion: int
    ) -> int:
        """
        Procesa una sección, detecta datos, genera gráficos y los añade al doc.
        
        Args:
            titulo_seccion: Título de la sección
            contenido: Contenido de texto
            doc: Objeto Document de python-docx
            numero_seccion: Número de la sección
        
        Returns:
            Número de gráficos añadidos
        """
        from docx.shared import Inches
        
        graficos_añadidos = 0
        
        # Añadir título de sección
        doc.add_heading(titulo_seccion, level=1)
        
        # Dividir contenido en párrafos
        parrafos = contenido.split('\n\n')
        
        for i, parrafo in enumerate(parrafos):
            if not parrafo.strip():
                continue
            
            # Añadir párrafo
            doc.add_paragraph(parrafo.strip())
            
            # Cada 2-3 párrafos, intentar extraer datos y generar gráfico
            if i > 0 and i % 2 == 0 and graficos_añadidos < 2:  # Max 2 gráficos por sección
                try:
                    # Detectar y extraer datos del contexto acumulado
                    contexto = '\n'.join(parrafos[:i+1])
                    datos_visual = await self.extractor.detectar_y_extraer_datos(
                        contexto, 
                        titulo_seccion
                    )
                    
                    if datos_visual:
                        logging.info(f"✅ Datos encontrados en '{titulo_seccion}': {datos_visual['tipo']}")
                        
                        # Generar gráfico
                        imagen_buffer = self.generador.generar_grafico(datos_visual)
                        
                        # Insertar en Word
                        doc.add_paragraph()  # Espacio
                        doc.add_picture(imagen_buffer, width=Inches(5.5))
                        
                        # Centrar imagen
                        last_paragraph = doc.paragraphs[-1]
                        last_paragraph.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER
                        
                        # Añadir pie de figura
                        caption = doc.add_paragraph(
                            f"Figura {numero_seccion}.{graficos_añadidos + 1}: {datos_visual['titulo']}"
                        )
                        caption.alignment = 1
                        caption.runs[0].italic = True
                        caption.runs[0].font.size = Pt(10)
                        
                        doc.add_paragraph()  # Espacio después
                        graficos_añadidos += 1
                        
                        logging.info(f"✅ Gráfico {graficos_añadidos} añadido a sección {numero_seccion}")
                
                except Exception as e:
                    logging.error(f"Error generando gráfico en sección {numero_seccion}: {e}")
                    continue
        
        return graficos_añadidos


# Función auxiliar para usar desde brain_v2.py
async def añadir_graficos_inteligentes(
    doc, 
    secciones: List[Dict], 
    client, 
    context=None, 
    chat_id=None
):
    """
    Añade gráficos inteligentes a un documento Word basándose en el contenido.
    
    Args:
        doc: Documento Word (python-docx)
        secciones: Lista de dicts con 'titulo', 'contenido', 'numero'
        client: Cliente de Mistral
        context: Context de Telegram (opcional, para reporting)
        chat_id: ID de chat (opcional, para reporting)
    
    Returns:
        Número total de gráficos añadidos
    """
    from docx.shared import Pt
    
    integrador = IntegradorGraficosWord(client)
    total_graficos = 0
    
    for seccion in secciones:
        try:
            if context and chat_id:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔍 Buscando datos visualizables en: {seccion['titulo'][:50]}..."
                )
            
            num_graficos = await integrador.procesar_seccion_con_graficos(
                titulo_seccion=seccion['titulo'],
                contenido=seccion['contenido'],
                doc=doc,
                numero_seccion=seccion['numero']
            )
            
            total_graficos += num_graficos
            
            if num_graficos > 0 and context and chat_id:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ {num_graficos} gráfico(s) añadido(s) a la sección {seccion['numero']}"
                )
        
        except Exception as e:
            logging.error(f"Error procesando sección {seccion.get('numero', '?')}: {e}")
            continue
    
    return total_graficos
