r"""Cattura SINGOLA dell'area interna della finestra Metin2 attiva.

Windows 10/11. Dipendenze: mss e Pillow, gia' installate nel progetto.
Avvio: .venv\Scripts\python.exe cattura_metin.py
Dopo Invio hai 5 secondi per portare Metin2 in primo piano, anche con Alt+Tab.
La finestra deve essere interamente visibile e ferma al momento dello scatto.

Questo script legge i pixel visibili: finestre sovrapposte possono comparire
nella cattura. Non legge la memoria del gioco e non invia click o tasti.
Non esegue OCR. Salva un nuovo PNG senza sovrascrivere quelli precedenti.
Le coordinate del PNG partono dall'angolo interno superiore sinistro del gioco.
"""

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import sys
import time


def api_windows():
    """Definisce tipi espliciti: gli identificatori finestra sono a 64 bit."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    firme = {
        "GetForegroundWindow": ([], wintypes.HWND),
        "GetWindowTextLengthW": ([wintypes.HWND], ctypes.c_int),
        "GetWindowTextW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        "IsWindow": ([wintypes.HWND], wintypes.BOOL),
        "IsIconic": ([wintypes.HWND], wintypes.BOOL),
        "GetClientRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "ClientToScreen": ([wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
        "SetThreadDpiAwarenessContext": ([ctypes.c_void_p], ctypes.c_void_p),
    }
    for nome, (argtypes, restype) in firme.items():
        funzione = getattr(user32, nome)
        funzione.argtypes = argtypes
        funzione.restype = restype
    # Coordinate fisiche anche con il ridimensionamento Windows al 125/150%.
    # Il processo termina dopo lo scatto; questa impostazione riguarda il suo thread.
    if not user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4)):
        raise ctypes.WinError(ctypes.get_last_error())
    return user32


def area_interna(user32, hwnd):
    """Ottiene dimensioni interne e posizione attuale sul desktop."""
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        raise RuntimeError("La finestra e' chiusa o ridotta a icona. Riprova.")
    rect = wintypes.RECT()
    origine = wintypes.POINT(0, 0)
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.ClientToScreen(hwnd, ctypes.byref(origine)):
        raise ctypes.WinError(ctypes.get_last_error())
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError("La finestra non ha un'area catturabile.")
    return {"left": origine.x, "top": origine.y, "width": w, "height": h}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attesa", type=int, default=5, choices=range(1, 31),
                        metavar="1-30", help="Secondi per scegliere la finestra (default 5)")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Questo script richiede Windows 10/11.")
    user32 = api_windows()
    import mss
    from PIL import Image

    print("Porta Metin2 in primo piano. Lascia tutta la finestra visibile.", flush=True)
    for secondi in range(args.attesa, 0, -1):
        print(f"Cattura tra {secondi}...", flush=True)
        time.sleep(1)

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("Nessuna finestra attiva. Riprova.")
    titolo = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
    user32.GetWindowTextW(hwnd, titolo, len(titolo))
    if "metin2" not in titolo.value.casefold():
        raise RuntimeError(f"La finestra attiva e' {titolo.value!r}, non Metin2. "
                           "Rilancia e passa al gioco durante il conto alla rovescia.")

    with mss.mss() as cattura:
        area = area_interna(user32, hwnd)
        # Per il primo test chiediamo una finestra contenuta in un solo monitor.
        contenuta = any(
            area["left"] >= m["left"] and area["top"] >= m["top"]
            and area["left"] + area["width"] <= m["left"] + m["width"]
            and area["top"] + area["height"] <= m["top"] + m["height"]
            for m in cattura.monitors[1:]
        )
        if not contenuta:
            raise RuntimeError("Metti tutta la finestra del gioco dentro un solo monitor e riprova.")
        if user32.GetForegroundWindow() != hwnd:
            raise RuntimeError("La finestra attiva e' cambiata. Riprova.")
        scatto = cattura.grab(area)
        if area_interna(user32, hwnd) != area or user32.GetForegroundWindow() != hwnd:
            raise RuntimeError("La finestra si e' spostata o ha perso il primo piano. Riprova.")

    immagine = Image.frombytes("RGB", scatto.size, scatto.rgb)
    percorso = Path(__file__).resolve().parent / (
        "cattura_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png")
    with percorso.open("xb") as destinazione:
        immagine.save(destinazione, format="PNG")
    print(f"\nCattura completata: {titolo.value}")
    print(f"Dimensioni: {immagine.width} x {immagine.height} pixel")
    print(f"Apri: {percorso}")
    print("Controlla che si veda il gioco, senza immagini nere o finestre sovrapposte.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCattura annullata.")
        raise SystemExit(130)
    except (OSError, RuntimeError, ImportError, AttributeError) as errore:
        print(f"Errore: {errore}")
        raise SystemExit(1)
