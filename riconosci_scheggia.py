r"""Primo esperimento: screenshot -> OCR -> rettangoli e coordinate.

Windows, Python 3.12 a 64 bit. Installazione nel terminale della cartella:
  py -3.12 -m venv .venv
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  .venv\Scripts\python.exe -m pip install easyocr==1.7.2 Pillow

Esecuzione:
  .venv\Scripts\python.exe riconosci_scheggia.py screenshot.png
Ritaglio facoltativo (x, y, larghezza, altezza, in pixel dello screenshot):
  .venv\Scripts\python.exe riconosci_scheggia.py screenshot.png --roi 200 100 1000 700

Il primo avvio scarica i modelli EasyOCR e richiede Internet.
L'elaborazione usa la CPU; non interagisce con il gioco.
Output: una NUOVA cartella debug_TIMESTAMP con risultato.png e letture.json.
Arresto: Ctrl+C nel terminale. Non e' una hotkey globale nel gioco.

Limiti: niente cattura live, click, gestione temporale o separazione delle
etichette sovrapposte. Una scritta in chat puo' sembrare un oggetto: usa ROI.
Le coordinate si riferiscono al file originale, NON al desktop.
Documentazione: https://www.jaided.ai/easyocr/documentation/
"""

import argparse
from datetime import datetime
from difflib import SequenceMatcher
import json
import math
from pathlib import Path
import unicodedata

TARGET = "Scheggia Pietra d. drago"


def normalizza(testo):
    """Ignora maiuscole, spazi, punteggiatura e accenti per il confronto."""
    testo = unicodedata.normalize("NFKD", testo.casefold())
    return "".join(c for c in testo if c.isalnum())


def somiglianza(testo):
    """Confronta tutta la lettura: piccoli errori abbassano il punteggio."""
    return SequenceMatcher(None, normalizza(testo), normalizza(TARGET)).ratio()


def coordinate_originali(punti, scala, offset, dimensioni):
    """Annulla l'ingrandimento OCR e riaggiunge l'origine del ritaglio."""
    ox, oy = offset
    larghezza, altezza = dimensioni
    xs = [float(p[0]) / scala + ox for p in punti]
    ys = [float(p[1]) / scala + oy for p in punti]
    x1 = max(0, min(larghezza - 1, math.floor(min(xs))))
    y1 = max(0, min(altezza - 1, math.floor(min(ys))))
    x2 = max(x1, min(larghezza - 1, math.ceil(max(xs))))
    y2 = max(y1, min(altezza - 1, math.ceil(max(ys))))
    return [x1, y1, x2, y2], [(x1 + x2) / 2, (y1 + y2) / 2]


def argomenti():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("immagine", type=Path)
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--scala", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument("--soglia", type=float, default=0.85,
                        help="Somiglianza minima (0-1), inizialmente 0.85")
    parser.add_argument("--confidenza", type=float, default=0.30,
                        help="Confidenza OCR minima (0-1), inizialmente 0.30")
    args = parser.parse_args()
    if not 0 <= args.soglia <= 1 or not 0 <= args.confidenza <= 1:
        parser.error("Soglia e confidenza devono essere comprese tra 0 e 1.")
    return args


def main():
    args = argomenti()
    # Import qui: le funzioni di confronto e coordinate non dipendono dall'OCR.
    import numpy as np
    from PIL import Image, ImageDraw, ImageOps
    import easyocr

    with Image.open(args.immagine) as sorgente:
        originale = ImageOps.exif_transpose(sorgente).convert("RGB")
    w, h = originale.size
    x, y, rw, rh = args.roi if args.roi is not None else (0, 0, w, h)
    if x < 0 or y < 0 or rw <= 0 or rh <= 0 or x + rw > w or y + rh > h:
        raise ValueError(f"ROI non valida: deve essere contenuta nell'immagine {w}x{h}.")
    area = originale.crop((x, y, x + rw, y + rh))
    area = area.resize((rw * args.scala, rh * args.scala), Image.Resampling.LANCZOS)

    print("Caricamento OCR su CPU; il primo avvio scarica i modelli...", flush=True)
    reader = easyocr.Reader(["it", "en"], gpu=False)
    print("Ricerca e lettura delle zone di testo...", flush=True)
    # readtext usa un rilevatore di testo e riconosce le regioni individuate.
    # paragraph=False conserva una confidenza per ciascuna lettura.
    # width_ths aiuta a riunire parole vicine; non risolve sovrapposizioni.
    risultati = reader.readtext(np.asarray(area), detail=1, paragraph=False,
                               width_ths=0.7, canvas_size=max(area.size))

    debug = originale.copy()
    disegno = ImageDraw.Draw(debug)
    disegno.rectangle((x, y, x + rw - 1, y + rh - 1), outline="cyan", width=2)
    letture = []
    for indice, (punti, testo, confidenza) in enumerate(risultati, start=1):
        sim = somiglianza(testo)
        trovato = sim >= args.soglia and float(confidenza) >= args.confidenza
        box, centro = coordinate_originali(punti, args.scala, (x, y), (w, h))
        voce = {"id": indice, "testo": testo, "confidenza_ocr": float(confidenza),
                "somiglianza": sim, "candidato": trovato,
                "box_xyxy": box, "centro_xy": centro}
        letture.append(voce)
        colore = "lime" if trovato else "orange"
        disegno.rectangle(box, outline=colore, width=3 if trovato else 1)
        # Il numero collega il rettangolo alla lettura nel terminale/JSON.
        disegno.text((box[0], max(0, box[1] - 12)), str(indice), fill=colore,
                     stroke_width=1, stroke_fill="black")
        if trovato:
            cx, cy = centro
            disegno.line((cx - 5, cy, cx + 5, cy), fill="red", width=2)
            disegno.line((cx, cy - 5, cx, cy + 5), fill="red", width=2)
        stato = "CANDIDATO" if trovato else "scartato"
        print(f"{indice}: {stato} | {testo!r} | OCR={float(confidenza):.3f} "
              f"| somiglianza={sim:.3f} | centro={centro}")

    # Ogni avvio ha la propria cartella: nessun risultato precedente sovrascritto.
    output = Path.cwd() / ("debug_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output.mkdir()
    debug.save(output / "risultato.png")
    rapporto = {"immagine": str(args.immagine.resolve()), "target": TARGET,
                "coordinate": "pixel immagine originale; origine alto-sinistra",
                "roi_xywh": [x, y, rw, rh], "scala": args.scala,
                "soglia_somiglianza": args.soglia, "soglia_ocr": args.confidenza,
                "letture": letture}
    (output / "letture.json").write_text(json.dumps(rapporto, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"\nCandidati: {sum(v['candidato'] for v in letture)}")
    print(f"Apri: {output / 'risultato.png'}")
    print("Verde=candidato, arancione=altra lettura, ciano=area analizzata.")
    print("I punteggi non sono probabilita' di aver trovato l'oggetto.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrotto dal terminale.")
        raise SystemExit(130)
    except (OSError, ValueError, ImportError) as errore:
        print(f"Errore: {errore}")
        raise SystemExit(1)
