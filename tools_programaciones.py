import os
import re
import logging
from dataclasses import dataclass
from typing import List

from pypdf import PdfReader

RUTA_PROGRAMACIONES = "/app/documentos/programaciones"
MAX_CARACTERES_CONTEXTO = 6000
STOPWORDS = {
    "de", "la", "el", "los", "las", "y", "o", "u", "en", "a", "para", "por", "con",
    "del", "al", "que", "se", "un", "una", "unos", "unas", "como", "sobre", "me", "mi",
    "mis", "tu", "tus", "su", "sus", "es", "son", "qué", "cual", "cuales", "cuáles",
    "donde", "dónde", "cuando", "cuándo", "resultado", "resultados", "aprendizaje", "asignatura",
}


@dataclass
class Fragmento:
    archivo: str
    pagina: int
    texto: str


def _normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _tokens_relevantes(texto: str) -> set[str]:
    tokens = re.findall(r"[a-záéíóúñ0-9]{3,}", _normalizar(texto))
    return {tok for tok in tokens if tok not in STOPWORDS}


def _extraer_fragmentos_pdf(ruta_pdf: str) -> List[Fragmento]:
    fragmentos: List[Fragmento] = []
    reader = PdfReader(ruta_pdf)
    for i, page in enumerate(reader.pages, start=1):
        texto = page.extract_text() or ""
        texto = re.sub(r"\n+", "\n", texto)
        for bloque in re.split(r"\n{2,}", texto):
            limpio = bloque.strip()
            if len(limpio) < 120:
                continue
            fragmentos.append(Fragmento(archivo=os.path.basename(ruta_pdf), pagina=i, texto=limpio))
    return fragmentos


def _cargar_fragmentos_programaciones() -> List[Fragmento]:
    if not os.path.isdir(RUTA_PROGRAMACIONES):
        return []

    fragmentos: List[Fragmento] = []
    for root, _, files in os.walk(RUTA_PROGRAMACIONES):
        for nombre in files:
            if not nombre.lower().endswith(".pdf"):
                continue
            ruta_pdf = os.path.join(root, nombre)
            try:
                fragmentos.extend(_extraer_fragmentos_pdf(ruta_pdf))
            except Exception as exc:
                logging.warning("No se pudo leer %s: %s", ruta_pdf, exc)
    return fragmentos


def buscar_contexto_programaciones(pregunta: str, max_fragmentos: int = 5) -> str:
    fragmentos = _cargar_fragmentos_programaciones()
    if not fragmentos:
        return ""

    tokens_pregunta = _tokens_relevantes(pregunta)
    if not tokens_pregunta:
        return ""

    def puntuar(frag: Fragmento) -> int:
        texto_norm = _normalizar(frag.texto)
        tokens_texto = set(re.findall(r"[a-záéíóúñ0-9]{3,}", texto_norm))
        inter = tokens_pregunta & tokens_texto
        score = len(inter)

        archivo_norm = _normalizar(frag.archivo)
        score += sum(1 for t in tokens_pregunta if t in archivo_norm)

        if "resultado" in tokens_pregunta and "ra" in texto_norm:
            score += 1
        return score

    mejores = sorted(fragmentos, key=puntuar, reverse=True)
    mejores = [f for f in mejores if puntuar(f) > 0][:max_fragmentos]

    if not mejores:
        return ""

    bloques = []
    total = 0
    for frag in mejores:
        encabezado = f"[{frag.archivo} · p.{frag.pagina}]"
        bloque = f"{encabezado}\n{frag.texto}"
        if total + len(bloque) > MAX_CARACTERES_CONTEXTO:
            break
        bloques.append(bloque)
        total += len(bloque)

    return "\n\n".join(bloques)


def responder_pregunta_programaciones(pregunta: str, client, modelo: str) -> str:
    contexto = buscar_contexto_programaciones(pregunta)
    if not contexto:
        return (
            "No he encontrado contenido relevante en /app/documentos/programaciones. "
            "Verifica que los PDF existen y contienen texto seleccionable."
        )

    prompt = (
        "Responde únicamente con la información del contexto proporcionado. "
        "Si no hay datos suficientes, dilo explícitamente. "
        "Respuesta en español clara y breve.\n\n"
        f"Pregunta: {pregunta}\n\n"
        f"Contexto:\n{contexto}"
    )

    try:
        res = client.chat.complete(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return res.choices[0].message.content
    except Exception as exc:
        logging.error("Error respondiendo sobre programaciones: %s", exc)
        return "No he podido procesar ahora mismo las programaciones."
