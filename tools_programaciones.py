"""
tools_programaciones.py — Búsqueda en PDFs de programaciones didácticas.

Bugs corregidos respecto a la versión anterior:
  1. "resultado/resultados/aprendizaje/asignatura" eran stopwords → ahora son tokens clave.
  2. Sin normalización de acentos → "programacion" no matcheaba "programación" en el PDF.
  3. Fragmentos < 120 chars filtrados → eliminaba líneas cortas de RA ("RA 1. Reconoce...").
  4. Sin boost por nombre de archivo → no priorizaba el módulo mencionado en la pregunta.
  5. Sin bigrams → "resultados de aprendizaje" se dividía en tokens individuales débiles.
"""

import os
import re
import logging
import unicodedata
from dataclasses import dataclass
from typing import List, Set

from pypdf import PdfReader

RUTA_PROGRAMACIONES = "/app/documentos/programaciones"
MAX_CARACTERES_CONTEXTO = 12000   # ampliado para capturar más contexto
MIN_LONGITUD_FRAGMENTO = 40       # bajado de 120 — los RA son líneas cortas

# ── Stopwords: solo palabras vacías genéricas.
# NO incluir términos de dominio como resultado/aprendizaje/asignatura.
STOPWORDS: Set[str] = {
    "de", "la", "el", "los", "las", "y", "o", "u", "en", "a", "para", "por", "con",
    "del", "al", "que", "se", "un", "una", "unos", "unas", "como", "sobre", "me", "mi",
    "mis", "tu", "tus", "su", "sus", "es", "son", "cual", "cuales", "donde", "cuando",
    "hay", "has", "han", "fue", "ser", "esta", "este", "ese", "esos", "esas",
}

# Frases compuestas que se tratan como un solo token para mejorar la precisión.
BIGRAMS = [
    ("resultados", "aprendizaje"),
    ("resultado", "aprendizaje"),
    ("unidades", "programacion"),
    ("criterios", "evaluacion"),
    ("objetivos", "generales"),
    ("competencias", "profesionales"),
    ("instrumentos", "evaluacion"),
    ("contenidos", "curriculares"),
    ("elementos", "transversales"),
    ("metodologias", "agiles"),
    ("control", "versiones"),
    ("diagramas", "clases"),
    ("diagramas", "comportamiento"),
]


@dataclass
class Fragmento:
    archivo: str
    pagina: int
    texto: str


# ── Normalización ─────────────────────────────────────────────────────────────

def _quitar_acentos(texto: str) -> str:
    """Convierte é→e, ó→o, etc. para matching insensible a acentos."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _normalizar(texto: str) -> str:
    """Minúsculas + sin acentos + espacios colapsados."""
    texto = texto.lower()
    texto = _quitar_acentos(texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _tokens_relevantes(texto: str) -> Set[str]:
    """
    Extrae tokens significativos de un texto:
    - Palabras ≥ 3 chars no stopwords
    - Bigrams compuestos (resultado_aprendizaje, etc.)
    """
    norm = _normalizar(texto)
    tokens = {
        tok
        for tok in re.findall(r"[a-z0-9]{3,}", norm)
        if tok not in STOPWORDS
    }
    # Añadir bigrams si ambas palabras aparecen en el texto
    for a, b in BIGRAMS:
        if a in norm and b in norm:
            tokens.add(f"{a}_{b}")
    return tokens


# ── Extracción de PDF ─────────────────────────────────────────────────────────

def _extraer_fragmentos_pdf(ruta_pdf: str) -> List[Fragmento]:
    """
    Extrae fragmentos de texto de un PDF por páginas.
    Fragmentos cortos (RA, CE, UP) se preservan si superan MIN_LONGITUD_FRAGMENTO.
    """
    fragmentos: List[Fragmento] = []
    try:
        reader = PdfReader(ruta_pdf)
    except Exception as exc:
        logging.warning("No se pudo leer %s: %s", ruta_pdf, exc)
        return fragmentos

    nombre = os.path.basename(ruta_pdf)

    for i, page in enumerate(reader.pages, start=1):
        texto_raw = page.extract_text() or ""

        # Normalizar saltos de línea dobles
        texto_raw = re.sub(r"\n{3,}", "\n\n", texto_raw)

        # Dividir en bloques por párrafo doble (o sección)
        bloques = re.split(r"\n{2,}", texto_raw)

        for bloque in bloques:
            limpio = bloque.strip()
            if len(limpio) < MIN_LONGITUD_FRAGMENTO:
                continue
            fragmentos.append(Fragmento(archivo=nombre, pagina=i, texto=limpio))

        # Además, extraer líneas individuales que parezcan RA/CE/UP
        # (para capturar "RA 1. Reconoce..." que puede quedar en líneas cortas)
        for linea in texto_raw.splitlines():
            limpio = linea.strip()
            if re.match(r"^(RA|CE|UP|RAT)\s*\d", limpio) and len(limpio) >= MIN_LONGITUD_FRAGMENTO:
                frag = Fragmento(archivo=nombre, pagina=i, texto=limpio)
                fragmentos.append(frag)

    return fragmentos


def _cargar_fragmentos_programaciones() -> List[Fragmento]:
    if not os.path.isdir(RUTA_PROGRAMACIONES):
        logging.warning("Carpeta de programaciones no encontrada: %s", RUTA_PROGRAMACIONES)
        return []

    fragmentos: List[Fragmento] = []
    for root, _, files in os.walk(RUTA_PROGRAMACIONES):
        for nombre in sorted(files):
            if not nombre.lower().endswith(".pdf"):
                continue
            ruta_pdf = os.path.join(root, nombre)
            try:
                nuevos = _extraer_fragmentos_pdf(ruta_pdf)
                fragmentos.extend(nuevos)
                logging.debug("Cargados %d fragmentos de %s", len(nuevos), nombre)
            except Exception as exc:
                logging.warning("Error leyendo %s: %s", nombre, exc)

    logging.info("Total fragmentos de programaciones: %d", len(fragmentos))
    return fragmentos


# ── Búsqueda y puntuación ─────────────────────────────────────────────────────

def _puntuar(frag: Fragmento, tokens_pregunta: Set[str]) -> int:
    """
    Puntuación de relevancia de un fragmento para una pregunta.

    Criterios (en orden de peso):
      4 pts  — bigram compuesto matchea en el texto
      2 pts  — token matchea en el nombre del archivo (boost de módulo)
      1 pt   — token matchea en el contenido del fragmento
    """
    texto_norm = _normalizar(frag.texto)
    tokens_texto = set(re.findall(r"[a-z0-9]{3,}", texto_norm))

    # Añadir bigrams presentes en el fragmento
    for a, b in BIGRAMS:
        if a in texto_norm and b in texto_norm:
            tokens_texto.add(f"{a}_{b}")

    archivo_norm = _normalizar(frag.archivo)

    score = 0
    for tok in tokens_pregunta:
        if "_" in tok:
            # Bigram: vale doble si aparece en el texto
            if tok in tokens_texto:
                score += 4
        elif tok in archivo_norm:
            # El token está en el nombre del archivo (ej: "despliegue")
            score += 2
        elif tok in tokens_texto:
            score += 1

    return score


def buscar_contexto_programaciones(pregunta: str, max_fragmentos: int = 8) -> str:
    """
    Devuelve el contexto más relevante de los PDFs de programaciones
    para responder la pregunta dada.
    """
    fragmentos = _cargar_fragmentos_programaciones()
    if not fragmentos:
        return ""

    tokens_pregunta = _tokens_relevantes(pregunta)
    if not tokens_pregunta:
        logging.warning("Sin tokens útiles en la pregunta: %s", pregunta)
        return ""

    logging.debug("Tokens de búsqueda: %s", tokens_pregunta)

    # Puntuar y filtrar
    puntuados = [
        (frag, _puntuar(frag, tokens_pregunta))
        for frag in fragmentos
    ]
    puntuados = [(f, s) for f, s in puntuados if s > 0]
    puntuados.sort(key=lambda x: x[1], reverse=True)

    if not puntuados:
        logging.info("Sin fragmentos relevantes para: %s", pregunta)
        return ""

    # Construir contexto respetando el límite de caracteres
    bloques = []
    total = 0
    archivos_usados: Set[str] = set()

    for frag, score in puntuados[:max_fragmentos]:
        encabezado = f"[{frag.archivo} · p.{frag.pagina}]"
        bloque = f"{encabezado}\n{frag.texto}"
        if total + len(bloque) > MAX_CARACTERES_CONTEXTO:
            break
        bloques.append(bloque)
        archivos_usados.add(frag.archivo)
        total += len(bloque)
        logging.debug("  score=%d archivo=%s p.%d", score, frag.archivo, frag.pagina)

    logging.info(
        "Contexto construido: %d fragmentos, %d chars, archivos: %s",
        len(bloques), total, archivos_usados,
    )
    return "\n\n".join(bloques)


def responder_pregunta_programaciones(pregunta: str, client, modelo: str) -> str:
    """
    Busca contexto en los PDFs de programaciones y usa la IA para responder.
    """
    contexto = buscar_contexto_programaciones(pregunta)

    if not contexto:
        return (
            "❌ No he encontrado contenido relevante en las programaciones.\n\n"
            "Comprueba que:\n"
            "• La carpeta /app/documentos/programaciones existe\n"
            "• Contiene archivos PDF con texto seleccionable (no escaneados)\n"
            "• El nombre del PDF incluye el nombre del módulo (ej: Despliegue.pdf)"
        )

    prompt = (
        "Eres un asistente para un docente de FP. "
        "Responde la pregunta usando ÚNICAMENTE la información del contexto proporcionado. "
        "Si no hay datos suficientes, dilo claramente y menciona qué sí encontraste. "
        "Sé específico, cita las secciones relevantes y organiza la respuesta con claridad.\n\n"
        f"Pregunta: {pregunta}\n\n"
        f"Contexto extraído de las programaciones:\n{contexto}"
    )

    try:
        res = client.chat.complete(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return res.choices[0].message.content
    except Exception as exc:
        logging.error("Error respondiendo sobre programaciones: %s", exc)
        return "❌ No he podido procesar la consulta ahora mismo."