import os
import copy
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from music21 import clef, duration, key, meter, note, stream, tempo
from openpyxl import Workbook

TONALITATS = [
    ("C", "major"), ("G", "major"), ("D", "major"), ("A", "major"),
    ("F", "major"), ("B-", "major"), ("E-", "major"),
    ("A", "minor"), ("E", "minor"), ("B", "minor"), ("F#", "minor"),
    ("D", "minor"), ("G", "minor"), ("C", "minor"),
]

FORMES = ["ABA", "ABC", "AA", "AB"]
MIDI_MIN = 36
MIDI_MAX = 67

PATRONS = {
    2.0: [[1.0, 1.0], [0.5, 0.5, 1.0], [1.0, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5], [1.5, 0.5], [0.5, 1.5]],
    3.0: [[1.0, 1.0, 1.0], [1.5, 0.5, 1.0], [1.0, 0.5, 0.5, 1.0], [0.5, 0.5, 1.0, 1.0]],
    4.0: [[1.0, 1.0, 1.0, 1.0], [2.0, 1.0, 1.0], [1.0, 1.0, 2.0], [1.5, 0.5, 1.0, 1.0]],
}


def _escala_en_rango(ton_obj: key.Key):
    notas = []
    for octava in range(1, 6):
        for p in ton_obj.pitches:
            candidato = note.Note(p.nameWithOctave)
            candidato.octave = octava
            if MIDI_MIN <= candidato.pitch.midi <= MIDI_MAX:
                notas.append(candidato.pitch)
    notas = sorted(notas, key=lambda p: p.midi)
    dedup, vistos = [], set()
    for p in notas:
        if p.nameWithOctave not in vistos:
            vistos.add(p.nameWithOctave)
            dedup.append(p)
    return dedup


def _crear_seccion(escala, num_compases: int, max_beat: float):
    seccion = []
    idx = len(escala) // 2
    pic = min(len(escala) - 1, idx + random.randint(2, 5))
    mitad = max(1, num_compases // 2)

    for i in range(num_compases):
        m = stream.Measure(number=i + 1)
        patron = random.choice(PATRONS[max_beat])

        if i < mitad:
            destino = int(idx + (pic - idx) * (i / max(1, mitad - 1)))
        else:
            destino = int(pic - (pic - idx) * ((i - mitad) / max(1, num_compases - mitad - 1)))

        for d in patron:
            if random.random() < 0.05:
                m.append(note.Rest(quarterLength=float(d)))
                continue

            paso = random.choice([-2, -1, 1, 2])
            idx = max(0, min(len(escala) - 1, destino + paso))
            n = note.Note(escala[idx].nameWithOctave, quarterLength=float(d))
            if random.random() < 0.15:
                n.duration = duration.Duration(float(d))
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
    candidatos = ["mscore", "mscore3", "mscore4", "musescore"]
    salida_pdf = xml_path.with_suffix(".pdf")

    for binario in candidatos:
        cmd = shutil.which(binario)
        if not cmd:
            continue
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
    bpm = random.randint(72, 96)
    num_compases_seccion = random.choice([8, 12]) if len(forma) == 3 else random.choice([8, 12, 16])

    max_beat = float(compas.split("/")[0])
    ton_obj = key.Key(ton_nom, ton_modo)
    escala = _escala_en_rango(ton_obj)

    score = stream.Score(id="RobiPartitura")
    part = stream.Part(id="Fagot")
    part.append(clef.BassClef())
    part.append(ton_obj)
    part.append(meter.TimeSignature(compas))
    part.append(tempo.MetronomeMark(number=bpm))

    secciones = {k: _crear_seccion(escala, num_compases_seccion, max_beat) for k in set(forma)}

    contador = 1
    for bloque in forma:
        for m in secciones[bloque]:
            mc = copy.deepcopy(m)
            mc.number = contador
            part.append(mc)
            contador += 1

    score.append(part)
    score.makeAccidentals(inPlace=True)

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
        "TempoBPM": bpm,
        "Forma": forma,
        "CompasesPorSeccion": num_compases_seccion,
        "CompasesTotales": num_compases_seccion * len(forma),
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
