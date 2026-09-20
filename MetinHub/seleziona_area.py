r"""Seleziona un ritaglio su uno screenshot, senza eseguire OCR.

Avvio da MetinHub:
  .venv\Scripts\python.exe seleziona_area.py Screenshot2.png

Trascina il mouse sull'immagine. Invio o Conferma stampa le coordinate e
chiude la finestra; Esc annulla. Puoi ridisegnare il rettangolo prima di
confermare. Le coordinate sono pixel ORIGINALI del file, non del desktop.
La finestra del gioco dal vivo non viene ancora cercata o seguita.

Dipendenze: Pillow (gia' installata) e Tkinter (inclusa nell'installer
ufficiale Python Windows, salvo deselezione durante l'installazione).
"""

import argparse
import math
from pathlib import Path


def converti_roi(inizio, fine, originale, anteprima):
    """Riporta la selezione dall'anteprima ridotta ai pixel originali.

    Si usano due rapporti distinti per compensare gli arrotondamenti delle
    dimensioni dell'anteprima. Funziona trascinando in qualsiasi direzione.
    """
    w, h = originale
    pw, ph = anteprima
    ax, bx = sorted((max(0, min(pw, inizio[0])), max(0, min(pw, fine[0]))))
    ay, by = sorted((max(0, min(ph, inizio[1])), max(0, min(ph, fine[1]))))
    if bx - ax < 3 or by - ay < 3:
        return None
    x1, y1 = math.floor(ax * w / pw), math.floor(ay * h / ph)
    x2, y2 = min(w, math.ceil(bx * w / pw)), min(h, math.ceil(by * h / ph))
    return x1, y1, x2 - x1, y2 - y1


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("immagine", type=Path)
    args = parser.parse_args()
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageOps, ImageTk

    with Image.open(args.immagine) as file:
        originale = ImageOps.exif_transpose(file).convert("RGB")

    root = tk.Tk()
    root.title("MetinHub - Seleziona area sullo screenshot")
    root.resizable(False, False)
    # Spazio per istruzioni, pulsanti e barra delle applicazioni.
    max_w = max(200, min(1400, root.winfo_screenwidth() - 100))
    max_h = max(150, min(850, root.winfo_screenheight() - 260))
    anteprima = originale.copy()
    anteprima.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    pw, ph = anteprima.size
    foto = ImageTk.PhotoImage(anteprima, master=root)

    ttk.Label(root, text="Trascina un rettangolo. Per correggerlo, disegnalo di nuovo.",
              padding=8).pack()
    canvas = tk.Canvas(root, width=pw, height=ph, highlightthickness=0,
                       borderwidth=0, cursor="crosshair")
    canvas.pack()
    canvas.create_image(0, 0, image=foto, anchor="nw")
    rettangolo = canvas.create_rectangle(0, 0, 0, 0, outline="#00ffff", width=2)
    stato = tk.StringVar(value=f"Immagine originale: {originale.width} x {originale.height} pixel")
    ttk.Label(root, textvariable=stato, padding=8).pack()
    comandi = ttk.Frame(root, padding=8)
    comandi.pack()

    # Stato della selezione; nessuna cattura dello schermo o ciclo OCR.
    selezione = {"inizio": None, "roi": None, "trascinando": False}

    def punto(event):
        return max(0, min(pw, event.x)), max(0, min(ph, event.y))

    def aggiorna(event):
        if selezione["inizio"] is None or not selezione["trascinando"]:
            return
        fine = punto(event)
        inizio = selezione["inizio"]
        canvas.coords(rettangolo, *inizio, *fine)
        roi = converti_roi(inizio, fine, originale.size, anteprima.size)
        selezione["roi"] = roi
        if roi is None:
            stato.set("Trascina per selezionare un'area piu' grande.")
        else:
            x, y, w, h = roi
            stato.set(f"Pixel originali: X={x}   Y={y}   Larghezza={w}   Altezza={h}")

    def inizia(event):
        selezione.update(inizio=punto(event), roi=None, trascinando=True)
        conferma_btn.configure(state="disabled")
        aggiorna(event)

    def termina(event):
        aggiorna(event)
        selezione["trascinando"] = False
        conferma_btn.configure(state="normal" if selezione["roi"] else "disabled")

    def conferma(event=None):
        if selezione["roi"] is None or selezione["trascinando"]:
            return
        x, y, w, h = selezione["roi"]
        print(f"\nArea scelta: X={x}, Y={y}, larghezza={w}, altezza={h}")
        print(f"Parametri da aggiungere al comando OCR: --roi {x} {y} {w} {h}", flush=True)
        root.destroy()

    def annulla(event=None):
        print("Selezione annullata. Nessun file modificato.", flush=True)
        root.destroy()

    conferma_btn = ttk.Button(comandi, text="Conferma (Invio)", command=conferma, state="disabled")
    conferma_btn.pack(side="left", padx=8)
    ttk.Button(comandi, text="Annulla (Esc)", command=annulla).pack(side="left", padx=8)
    canvas.bind("<ButtonPress-1>", inizia)
    canvas.bind("<B1-Motion>", aggiorna)
    canvas.bind("<ButtonRelease-1>", termina)
    root.bind("<Return>", conferma)
    root.bind("<Escape>", annulla)
    root.protocol("WM_DELETE_WINDOW", annulla)
    print("Seleziona l'area nella finestra e premi Conferma.", flush=True)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ImportError) as errore:
        print(f"Errore: {errore}")
        raise SystemExit(1)
