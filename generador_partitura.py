import copy
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from music21 import clef, duration, dynamics, expressions, key, meter, note, stream, tempo
from music21.note import Rest as MusicRest
from music21 import articulations
from openpyxl import Workbook

TONALITATS = [
    ("C", "major"), ("G", "major"), ("D", "major"), ("A", "major"),
    ("F", "major"), ("B-", "major"), ("E-", "major"),
    ("A", "minor"), ("E", "minor"), ("B", "minor"), ("F#", "minor"),
    ("D", "minor"), ("G", "minor"), ("C", "minor"),
]
FORMES = ["ABA", "ABC", "AA", "AB"]

# Rang fagot: Do1 a Sol3 real -> C2-G4 en music21
MIDI_MIN = 36
MIDI_MAX = 67

# Incluye síncopas/contratiempos/tresillos para lecturas más realistas
PATRONS = {
    2.0: [
        [1.0, 1.0], [0.5, 0.5, 1.0], [1.0, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5],
        [1.5, 0.5], [0.5, 1.5], [0.75, 0.25, 1.0], [1.0, 0.75, 0.25],
        [0.5, 1.0, 0.5], [0.25, 0.5, 0.25, 1.0], [0.25, 0.25, 0.5, 1.0],
        ["T", 1.0], [1.0, "T"],
    ],
    3.0: [
        [1.0, 1.0, 1.0], [1.5, 0.5, 1.0], [1.0, 0.5, 0.5, 1.0],
        [0.5, 0.5, 1.0, 1.0], [1.0, 1.5, 0.5], [1.0, 0.75, 0.25, 1.0],
        [0.75, 0.25, 1.0, 1.0], [0.5, 1.0, 1.0, 0.5], [0.25, 0.25, 0.5, 1.0, 1.0],
        ["T", 1.0, 1.0], [1.0, "T", 1.0], [1.0, 1.0, "T"],
    ],
    4.0: [
        [1.0, 1.0, 1.0, 1.0], [2.0, 1.0, 1.0], [1.0, 1.0, 2.0],
        [1.5, 0.5, 1.0, 1.0], [1.0, 0.5, 0.5, 2.0], [0.5, 0.5, 0.5, 0.5, 1.0, 1.0],
        [1.0, 1.0, 0.5, 0.5, 1.0], [1.0, 0.75, 0.25, 1.0, 1.0],
        [0.5, 1.0, 1.0, 1.0, 0.5], [1.0, 0.5, 1.0, 0.5, 1.0],
        [0.25, 0.25, 0.5, 1.0, 1.0, 1.0],
        ["T", 1.0, 1.0, 1.0], [1.0, "T", 1.0, 1.0], [1.0, 1.0, "T", 1.0],
    ],
}


def _escala_en_rango(ton_obj: key.Key):
    notas = []
    for octava in range(1, 6):
        for grado, p in enumerate(ton_obj.pitches):
            pc = note.Note(p.name)
            pc.octave = octava
            if MIDI_MIN <= pc.pitch.midi <= MIDI_MAX:
                notas.append((pc.pitch.nameWithOctave, grado % 7))
    notas.sort(key=lambda x: note.Note(x[0]).pitch.midi)

    dedup, vistos = [], set()
    for nombre, grado in notas:
        if nombre not in vistos:
            vistos.add(nombre)
            dedup.append((nombre, grado))
    return dedup


def _nota_por_grado(escala, grado):
    cands = [i for i, (_n, g) in enumerate(escala) if g == grado]
    if not cands:
        return len(escala) // 2
    centro = len(escala) // 2
    return min(cands, key=lambda i: abs(i - centro))


def _mov_melodico(idx, largo, tipo="conjuntos"):
    if tipo == "conjuntos":
        delta = random.choices([-2, -1, -1, -1, 0, 1, 1, 1, 2], k=1)[0]
    elif tipo == "arpegio":
        delta = random.choice([-4, -2, 2, 4])
    else:
        delta = random.randint(-3, 3)
    return max(0, min(largo - 1, idx + delta))


def _agregar_articulacion(n):
    r = random.random()
    if r < 0.15:
        n.articulations.append(articulations.Staccato())
    elif r < 0.23:
        n.articulations.append(articulations.Tenuto())
    elif r < 0.28:
        n.articulations.append(articulations.Accent())


def _crear_seccion(escala, num_compases: int, max_beat: float):
    seccion = []
    centro = len(escala) // 2
    idx = random.randint(max(0, centro - 3), min(len(escala) - 1, centro + 3))
    pico = min(len(escala) - 1, centro + random.randint(3, 5))
    mitad = max(1, num_compases // 2)

    for i in range(num_compases):
        m = stream.Measure()
        patron = random.choice(PATRONS[max_beat])
        es_cadencia = i in (mitad - 1, num_compases - 1)
        grado_cad = 4 if i == mitad - 1 else 0

        if i < mitad:
            t = i / max(mitad - 1, 1)
            guia = int(centro + t * (pico - centro))
        else:
            t = (i - mitad) / max(num_compases - mitad - 1, 1)
            guia = int(pico - t * (pico - centro))
        idx = max(0, min(len(escala) - 1, idx + max(-2, min(2, guia - idx))))

        for j, d in enumerate(patron):
            if d == "T":
                for _ in range(3):
                    idx = _mov_melodico(idx, len(escala), "conjuntos")
                    n = note.Note(escala[idx][0], quarterLength=1 / 3)
                    n.duration.appendTuplet(duration.Tuplet(3, 2))
                    _agregar_articulacion(n)
                    m.append(n)
                continue

            es_ultimo = j == len(patron) - 1
            if es_cadencia and es_ultimo:
                idx = _nota_por_grado(escala, grado_cad)
            else:
                idx = _mov_melodico(idx, len(escala), "conjuntos")

            if random.random() < 0.06 and j == 0:
                m.append(MusicRest(quarterLength=float(d)))
            else:
                n = note.Note(escala[idx][0], quarterLength=float(d))
                _agregar_articulacion(n)
                m.append(n)

        seccion.append(m)
    return seccion


def _guardar_resumen_xlsx(destino: Path, metadatos: dict):
    wb = Workbook()
    ws = wb.active
    ws.title = "Partitura"
    ws.append(["Campo", "Valor"])
    for clave, valor in metadatos.items():
        ws.append([clave, str(valor)])
    wb.save(destino)
    return destino


def _musicxml_to_pdf(xml_path: Path):
    for binario in ["mscore", "mscore3", "mscore4", "musescore"]:
        cmd = shutil.which(binario)
        if not cmd:
            continue
        salida_pdf = xml_path.with_suffix(".pdf")
        try:
            subprocess.run([cmd, str(xml_path), "-o", str(salida_pdf)], check=True, capture_output=True)
            if salida_pdf.exists():
                return salida_pdf
        except Exception:
            continue
    return None


def generar_partitura_fagot(base_dir: str = "/app/documentos/partituras"):
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    ton_nom, ton_modo = random.choice(TONALITATS)
    compas = random.choice(["2/4", "3/4", "4/4"])
    forma = random.choice(FORMES)
    agogica = random.choice(["Andante", "Moderato"])
    bpm = random.randint(72, 84) if agogica == "Andante" else random.randint(88, 96)
    compases_seccion = random.choice([8, 12]) if len(forma) == 3 else random.choice([8, 12, 16])

    ton_obj = key.Key(ton_nom, ton_modo)
    escala = _escala_en_rango(ton_obj)
    if len(escala) < 7:
        return generar_partitura_fagot(base_dir=base_dir)

    score = stream.Score(id="RobiPartitura")
    part = stream.Part(id="Fagot")
    part.append(clef.BassClef())
    part.append(ton_obj)
    part.append(meter.TimeSignature(compas))
    part.append(tempo.MetronomeMark(text=agogica, number=bpm))

    config_forma = {
        "ABA": (["A", "B", "A"], ["f", "p", "f"]),
        "ABC": (["A", "B", "C"], ["f", "p", "mf"]),
        "AA": (["A", "A"], ["f", "p"]),
        "AB": (["A", "B"], ["f", "p"]),
    }
    orden, dyn_orden = config_forma[forma]

    max_beat = float(compas.split("/")[0])
    secciones = {}
    for letra in dict.fromkeys(orden):
        secciones[letra] = _crear_seccion(escala, compases_seccion, max_beat)

    contador = 1
    for i, bloque in enumerate(orden):
        sec = secciones[bloque]
        mitad = len(sec) // 2
        dyn_ini = dyn_orden[i]
        for j, m in enumerate(sec):
            mc = copy.deepcopy(m)
            mc.number = contador
            if j == 0:
                mc.insert(0, dynamics.Dynamic(dyn_ini))
            if j == mitad:
                mc.insert(0, dynamics.Crescendo() if dyn_ini == "p" else dynamics.Diminuendo())
            part.append(mc)
            contador += 1

    notas = list(part.flatten().notes)
    if notas:
        notas[-1].expressions.append(expressions.Fermata())

    medidas = list(part.getElementsByClass(stream.Measure))
    if medidas:
        medidas[-1].rightBarline = "final"

    score.append(part)
    score.makeAccidentals(
        useKeySignature=True,
        alteredPitches=ton_obj.alteredPitches,
        overrideStatus=True,
        cautionaryNotImmediateRepeat=False,
        inPlace=True,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ton_archivo = ton_nom.replace("-", "b").replace("#", "s")
    prefijo = f"partitura_fagot_{ton_archivo}_{ton_modo}_{stamp}"

    xml_path = base / f"{prefijo}.musicxml"
    xlsx_path = base / f"{prefijo}.xlsx"

    score.write("musicxml", fp=str(xml_path))

    metadatos = {
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Tonalidad": f"{ton_nom.replace('-', 'b')} {ton_modo}",
        "Compas": compas,
        "Agogica": agogica,
        "TempoBPM": bpm,
        "Forma": forma,
        "CompasesPorSeccion": compases_seccion,
        "CompasesTotales": compases_seccion * len(orden),
        "ArchivoMusicXML": str(xml_path),
    }
    _guardar_resumen_xlsx(xlsx_path, metadatos)
    pdf_path = _musicxml_to_pdf(xml_path)

    return {
        "xml": str(xml_path),
        "xlsx": str(xlsx_path),
        "pdf": str(pdf_path) if pdf_path else None,
        "meta": metadatos,
    }
