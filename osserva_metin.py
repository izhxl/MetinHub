r"""MetinHub: raccolta automatica con inseguimento visivo. Windows 10/11.
Avvio: .venv\Scripts\python.exe osserva_metin.py
Richiede i precedenti cattura_metin.py e riconosci_scheggia.py.
Avvia/Pausa dalla GUI; F8 stop. F6 facoltativo, nessun F7.
Auto confronta CPU e CUDA disponibile sul ritaglio, ogni 120 secondi.
GPU non disponibile o in errore: CPU con profilo 1 o 2 thread. Manutenzione da scheda Sistema.
Durante ogni tentativo segue una sola etichetta con template matching locale,
conservativo, fino a 8 secondi. Perdita visiva: rilascio regolabile, default 0.2 s; poi nuovo OCR.
Pressione mantenuta con puntatore che segue l’etichetta, massimo 8 secondi.
Timeout: bersaglio escluso per 8 secondi,
Ricerca live dopo il rilevamento; intervallo lungo solo dopo due letture OCR vuote.
La scomparsa NON conferma la raccolta. Anteprima aggiornata anche nel tracking.
Finestra visibile e monitor principale. Non recupera il focus automaticamente.
"""

import argparse
import ctypes
from ctypes import wintypes
import multiprocessing as mp
import os
from pathlib import Path
import queue
import sys
import threading
import time
import math
import logging
import json
from logging.handlers import RotatingFileHandler
from collections import deque

VERSIONE_NUMERO = (Path(__file__).resolve().parent / 'VERSION.txt').read_text(encoding='utf-8').strip()
VERSIONE = VERSIONE_NUMERO + ' - Pesca sperimentale'


class RegistroSuErrore(logging.Handler):
    """Ultimi 200 eventi in RAM; disco solo per errore o esportazione esplicita."""
    def __init__(self, percorso):
        super().__init__()
        self.eventi = deque(maxlen=200)
        self.file = RotatingFileHandler(percorso, maxBytes=1_000_000,
                                       backupCount=1, encoding='utf-8', delay=True)
        self.file.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))

    def emit(self, record):
        # Conserva testo e traceback gia formattati, senza trattenere frame/immagini.
        testo = logging.Formatter().format(record)
        copia = logging.LogRecord(record.name, record.levelno, record.pathname,
                                  record.lineno, testo[:20000], (), None)
        copia.created = record.created
        copia.msecs = record.msecs
        self.eventi.append(copia)
        if record.levelno >= logging.ERROR:
            self.salva('Rapporto automatico su errore')

    def salva(self, motivo):
        with self.lock:
            self.file.handle(logging.LogRecord('metinhub', logging.INFO, '', 0,
                                              motivo, (), None))
            for record in self.eventi:
                self.file.handle(record)
            self.file.flush()
            self.eventi.clear()

    def close(self):
        # logging.shutdown non deve scrivere il buffer di una sessione riuscita.
        self.file.close()
        super().close()


def prepara_registro():
    logger = logging.getLogger('metinhub')
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(RegistroSuErrore(Path(__file__).resolve().parent / 'metinhub_log.txt'))
    return logger


def threads_validi(valore):
    if valore not in (1, 2):
        raise ValueError('Scegli 1 thread (Leggera) oppure 2 thread (Normale).')
    return int(valore)


class StatoScansione:
    """Due letture OCR vuote chiudono la fase live, evitando una pausa al primo errore."""
    def __init__(self):
        self.live = False
        self.vuote = 0

    def aggiorna(self, numero_candidati):
        if numero_candidati:
            self.live = True
            self.vuote = 0
        elif self.live:
            self.vuote += 1
            if self.vuote >= 2:
                self.live = False


def rilascio_valido(valore):
    numero = float(str(valore).replace(',', '.'))
    if not math.isfinite(numero) or not 0.1 <= numero <= 1.5:
        raise ValueError('Il tempo di rilascio deve essere tra 0,1 e 1,5 secondi.')
    return numero


def intervallo_valido(valore):
    numero = float(str(valore).replace(',', '.'))
    if not math.isfinite(numero) or not 1 <= numero <= 3600:
        raise ValueError('Inserisci un intervallo tra 1 e 3600 secondi.')
    return numero


def leggi_impostazioni(percorso):
    if not percorso.exists():
        return {}
    dati = json.loads(percorso.read_text(encoding='utf-8'))
    if not isinstance(dati, dict):
        raise ValueError('Formato impostazioni non valido.')
    dati['intervallo_scan'] = intervallo_valido(dati.get('intervallo_scan', 10))
    dati['ritardo_rilascio'] = rilascio_valido(dati.get('ritardo_rilascio', 0.2))
    dati['threads_cpu'] = threads_validi(dati.get('threads_cpu', 2))
    if dati.get('motore', 'Auto') not in ('Auto', 'CPU', 'GPU'):
        raise ValueError('Motore salvato non valido.')
    return dati


def salva_impostazioni(percorso, intervallo, motore, ritardo_rilascio=0.2, threads_cpu=2, url_aggiornamenti=''):
    dati = dict(intervallo_scan=intervallo_valido(intervallo), motore=motore,
                ritardo_rilascio=rilascio_valido(ritardo_rilascio), threads_cpu=threads_validi(threads_cpu),
                url_aggiornamenti=url_aggiornamenti.strip())
    temporaneo = percorso.with_suffix('.tmp')
    temporaneo.write_text(json.dumps(dati, indent=2), encoding='utf-8')
    temporaneo.replace(percorso)


def converti_selezione(inizio, fine, originale, anteprima):
    """Converte il rettangolo ridotto nei pixel dell'area interna originale."""
    w, h = originale
    pw, ph = anteprima
    ax, bx = sorted((max(0, min(pw, inizio[0])), max(0, min(pw, fine[0]))))
    ay, by = sorted((max(0, min(ph, inizio[1])), max(0, min(ph, fine[1]))))
    if bx - ax < 3 or by - ay < 3:
        return None
    x, y = math.floor(ax * w / pw), math.floor(ay * h / ph)
    destra, basso = min(w, math.ceil(bx * w / pw)), min(h, math.ceil(by * h / ph))
    return (x, y, destra - x, basso - y)


def selettore_area(root, immagine, completato):
    """Finestra di selezione non bloccante: F8 rimane gestito dalla GUI."""
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk
    top = tk.Toplevel(root)
    top.title('Seleziona area - trascina sullo screenshot del gioco')
    top.resizable(False, False)
    anteprima = immagine.copy()
    anteprima.thumbnail((max(200, min(1400, top.winfo_screenwidth()-100)),
                         max(150, min(850, top.winfo_screenheight()-260))),
                        Image.Resampling.LANCZOS)
    foto = ImageTk.PhotoImage(anteprima, master=top)
    top.foto = foto
    ttk.Label(top, text='Trascina un rettangolo. Per correggerlo, disegnalo di nuovo.', padding=8).pack()
    canvas = tk.Canvas(top, width=anteprima.width, height=anteprima.height,
                       borderwidth=0, highlightthickness=0, cursor='crosshair')
    canvas.pack()
    canvas.create_image(0, 0, anchor='nw', image=foto)
    rett = canvas.create_rectangle(0, 0, 0, 0, outline='cyan', width=2)
    info = tk.StringVar(value='Coordinate relative all\'interno del gioco, in pixel originali.')
    ttk.Label(top, textvariable=info, padding=8).pack()
    barra = ttk.Frame(top, padding=8)
    barra.pack()
    dati = dict(inizio=None, roi=None, trascinando=False, finito=False)

    def muovi(event):
        if not dati['trascinando']:
            return
        fine = (max(0, min(anteprima.width, event.x)),
                max(0, min(anteprima.height, event.y)))
        canvas.coords(rett, *dati['inizio'], *fine)
        dati['roi'] = converti_selezione(dati['inizio'], fine, immagine.size, anteprima.size)
        if dati['roi']:
            x, y, w, h = dati['roi']
            info.set(f'X={x} | Y={y} | Larghezza={w} | Altezza={h}')
        else:
            info.set('Seleziona un rettangolo piu\' grande.')

    def inizia(event):
        dati.update(inizio=(event.x, event.y), roi=None, trascinando=True)
        bottone.configure(state='disabled')
        muovi(event)

    def rilascia(event):
        muovi(event)
        dati['trascinando'] = False
        bottone.configure(state='normal' if dati['roi'] else 'disabled')

    def fine(conferma):
        if dati['finito'] or (conferma and (not dati['roi'] or dati['trascinando'])):
            return
        dati['finito'] = True
        roi = dati['roi'] if conferma else None
        top.destroy()
        completato(roi)

    bottone = ttk.Button(barra, text='Conferma area (Invio)', state='disabled', command=lambda: fine(True))
    bottone.pack(side='left', padx=6)
    ttk.Button(barra, text='Annulla (Esc)', command=lambda: fine(False)).pack(side='left', padx=6)
    canvas.bind('<ButtonPress-1>', inizia)
    canvas.bind('<B1-Motion>', muovi)
    canvas.bind('<ButtonRelease-1>', rilascia)
    top.bind('<Return>', lambda event: fine(True))
    top.bind('<Escape>', lambda event: fine(False))
    top.protocol('WM_DELETE_WINDOW', lambda: fine(False))
    top.grab_set()
    top.lift()
    top.focus_force()
    return top


def regione_schermo(area, roi):
    """Somma origine finestra e ROI interna, controllando i limiti."""
    x, y, w, h = roi
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > area['width'] or y + h > area['height']:
        raise ValueError("L'area scelta non rientra nella finestra.")
    return dict(left=area['left'] + x, top=area['top'] + y, width=w, height=h)


def patch_stabile(prima, dopo):
    """Confronto locale conservativo; non prova che l'oggetto sia lo stesso."""
    from PIL import ImageChops, ImageStat
    if prima.size != dopo.size or min(prima.size) <= 0:
        return False
    diff = ImageChops.difference(prima.convert('RGB'), dopo.convert('RGB'))
    media = sum(ImageStat.Stat(diff).mean) / 3
    # Non nascondere la scomparsa del testo nella media dello sfondo scuro.
    a = list(prima.convert('L').getdata())
    b = list(dopo.convert('L').getdata())
    chiari = [i for i, v in enumerate(a) if v >= 170]
    conservati = sum(b[i] >= 150 for i in chiari) / max(1, len(chiari))
    return len(chiari) >= 8 and media <= 10 and conservati >= 0.85


def localizza(template, immagine, centro, raggio=90, diagnostica=None):
    """Segue il testo luminoso; fra duplicati privilegia la continuita' spaziale.

    Se due corrispondenze sono altrettanto vicine, torna all'OCR senza click.
    Il punteggio e' una correlazione sperimentale, non una probabilita'.
    """
    import cv2
    import numpy as np
    def motivo(testo):
        if diagnostica is not None:
            diagnostica['motivo'] = testo
    tw, th = template.size
    cx, cy = centro
    l, t = max(0, round(cx-tw/2-raggio)), max(0, round(cy-th/2-raggio))
    r, b = min(immagine.width, round(cx+tw/2+raggio)), min(immagine.height, round(cy+th/2+raggio))
    if min(tw, th) <= 1 or r-l < tw or b-t < th:
        motivo('ritaglio troppo piccolo o fuori area')
        return None
    def testo_luminoso(im):
        # Conserva anche testo rosso/giallo saturo, che in grigio puo'
        # risultare troppo scuro. Il cambio colore sotto il mouse e' tollerato.
        gray = np.asarray(im).max(axis=2).astype(np.uint8)
        # Riduce il contributo del terreno in movimento senza aggiornare il
        # template originale con immagini non confermate dall'OCR.
        contrasto = cv2.subtract(gray, cv2.GaussianBlur(gray, (0,0), 2))
        return ((gray >= 145) & (contrasto >= 12)).astype(np.uint8)*255
    needle = testo_luminoso(template)
    if np.count_nonzero(needle) < 12 or needle.std() < 8:
        motivo('troppi pochi pixel di testo luminoso nel ritaglio OCR')
        return None
    hay = testo_luminoso(immagine.crop((l,t,r,b)))
    scores = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
    scores = np.nan_to_num(scores, nan=-1, posinf=-1, neginf=-1)
    _, best, _, pos = cv2.minMaxLoc(scores)
    if best < 0.82:
        motivo(f'testo non ritrovato: correlazione {best:.2f}, richiesta 0.82')
        return None
    # Estrae massimi separati; etichette uguali non invalidano piu' tutte
    # le posizioni quando una e' chiaramente piu' vicina al bersaglio.
    posizioni = []
    other = scores.copy()
    for _ in range(12):
        _, score, _, pos = cv2.minMaxLoc(other)
        if score < max(0.82, best-0.05):
            break
        px, py = pos
        distanza = math.dist((l+px+tw/2, t+py+th/2), centro)
        posizioni.append((distanza, px, py, score))
        other[max(0,py-th//2):py+th//2+1, max(0,px-tw//2):px+tw//2+1] = -1
    posizioni.sort()
    if len(posizioni)>1 and posizioni[1][0]-posizioni[0][0]<max(6,th*0.35):
        motivo('due etichette indistinguibili alla stessa distanza: nuova lettura')
        return None
    _, px, py, score = posizioni[0]
    motivo(f'testo seguito: correlazione {score:.2f}')
    return (l+px, t+py, l+px+tw, t+py+th)


def candidati_disponibili(candidati, esclusi, adesso):
    """Esclusione breve e locale; ritorna anche il tempo di ripresa."""
    esclusi[:] = [(centro, fine) for centro, fine in esclusi if fine > adesso]
    disponibili = []
    attese = []
    for c in candidati:
        vicini = [fine for centro, fine in esclusi if math.dist(c[1], centro)<35]
        if vicini:
            attese.append(max(vicini)-adesso)
        else:
            disponibili.append(c)
    return disponibili, min(attese, default=0)


def imposta_pressione(user32, premuto, tenere):
    """Invia un solo DOWN per tratto continuo e un UP alla fine."""
    if tenere and not premuto.value:
        premuto.value = 1  # Il processo principale potra' rilasciare anche dopo un arresto forzato.
        user32.mouse_event(0x0002,0,0,0,0)
    elif not tenere and premuto.value:
        user32.mouse_event(0x0004,0,0,0,0)
        premuto.value = 0


def sposta_mouse_verificato(user32, x, y):
    """Controlla sia l'esito di Windows sia la posizione ottenuta."""
    # user32 proviene da WinDLL(use_last_error=True): leggere subito il
    # codice, prima che un'altra chiamata Windows lo possa sovrascrivere.
    ctypes.set_last_error(0)
    if not user32.SetCursorPos(x,y):
        codice = ctypes.get_last_error()
        descrizione = ctypes.FormatError(codice).strip() if codice else 'nessun codice aggiuntivo restituito'
        raise RuntimeError(f'SetCursorPos fallito a ({x},{y}); WinError={codice}: '
                           f'{descrizione}. Movimento annullato.')
    posizione = wintypes.POINT()
    ctypes.set_last_error(0)
    if not user32.GetCursorPos(ctypes.byref(posizione)):
        codice = ctypes.get_last_error()
        descrizione = ctypes.FormatError(codice).strip() if codice else 'nessun codice aggiuntivo restituito'
        raise RuntimeError(f'GetCursorPos fallito; WinError={codice}: {descrizione}. Movimento annullato.')
    if math.dist((posizione.x,posizione.y),(x,y)) > 3:
        raise RuntimeError(f'Mouse non arrivato al bersaglio: richiesto ({x},{y}), '
                           f'ottenuto ({posizione.x},{posizione.y}). Movimento annullato.')


class MotoreOCR:
    def __init__(self, modo, stato):
        import torch
        import easyocr
        self.torch, self.easyocr, self.stato = torch, easyocr, stato
        self.readers = {}
        self.modo = modo
        self.gpu = modo != 'CPU' and torch.cuda.is_available()
        self.scelto = 'CPU'
        self.prossimo = 0
        if not self.gpu:
            stato('CPU: CUDA non disponibile in questa installazione.' if modo != 'CPU' else 'CPU selezionata.')

    def leggi_con(self, nome, frame):
        if nome not in self.readers:
            self.stato('Caricamento ' + nome + '...')
            self.readers[nome] = self.easyocr.Reader(['it','en'], gpu=(nome == 'GPU'))
        return self.readers[nome].readtext(frame, detail=1, paragraph=False,
                    width_ths=0.7, canvas_size=max(frame.shape[:2]), workers=0)

    def leggi(self, frame):
        if self.gpu and self.modo == 'Auto' and time.monotonic() >= self.prossimo:
            import statistics
            tempi = {}
            self.stato('Confronto CPU/GPU: nessun click durante la misura...')
            for nome in ('CPU','GPU'):
                try:
                    self.leggi_con(nome, frame)  # riscaldamento escluso dalla misura
                    misure = []
                    for _ in range(2):
                        start = time.monotonic()
                        self.leggi_con(nome, frame)
                        if nome == 'GPU':
                            self.torch.cuda.synchronize()
                        misure.append(time.monotonic()-start)
                    tempi[nome] = statistics.median(misure)
                except Exception:
                    if nome == 'CPU':
                        raise
                    self.gpu = False
                    self.readers.pop('GPU', None)
                    self.torch.cuda.empty_cache()
            self.scelto = 'GPU' if tempi.get('GPU', float('inf')) < tempi['CPU']*0.85 else 'CPU'
            self.prossimo = time.monotonic()+120
        elif self.gpu and self.modo == 'GPU':
            self.scelto = 'GPU'
        try:
            result = self.leggi_con(self.scelto, frame)
        except Exception:
            if self.scelto != 'GPU':
                raise
            self.gpu = False
            self.readers.pop('GPU', None)
            self.torch.cuda.empty_cache()
            self.scelto = 'CPU'
            self.stato('Errore GPU: passaggio automatico alla CPU.')
            result = self.leggi_con('CPU', frame)
        return result


def worker(hwnd, dimensioni, roi, attivo, generazione, uscita, click_richiesto, modo, premuto, intervallo_scan, ritardo_rilascio, threads_cpu):
    for nome in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):
        os.environ[nome] = str(threads_validi(threads_cpu))
    ultimo_stato = None
    def stato(testo):
        nonlocal ultimo_stato
        if testo != ultimo_stato:
            uscita.put(('stato', testo))
            ultimo_stato = testo
    def dettaglio(testo):
        uscita.put(('dettaglio', testo))
    try:
        from cattura_metin import api_windows, area_interna
        from riconosci_scheggia import somiglianza, coordinate_originali
        import torch
        torch.set_num_threads(threads_cpu)
        torch.set_num_interop_threads(1)
        import cv2
        cv2.setNumThreads(1)
        import numpy as np
        import mss
        from PIL import Image, ImageDraw
        import pyautogui as mouse
        mouse.FAILSAFE = True
        mouse.PAUSE = 0
        u = api_windows()
        u.WindowFromPoint.argtypes = [wintypes.POINT]
        u.WindowFromPoint.restype = wintypes.HWND
        u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetAncestor.restype = wintypes.HWND
        u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        u.SetCursorPos.restype = wintypes.BOOL
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.restype = wintypes.BOOL
        motore = MotoreOCR(modo, stato)
        pressione_inizio = None
        def release():
            nonlocal pressione_inizio
            if premuto.value and pressione_inizio is not None:
                dettaglio(f'Rilascio effettivo dopo {time.monotonic()-pressione_inizio:.2f} s di pressione continua.')
            imposta_pressione(u, premuto, False)
            pressione_inizio = None
        def valido(epoca, area):
            try:
                return (attivo.is_set() and generazione.value == epoca and
                        u.IsWindow(hwnd) and not u.IsIconic(hwnd) and
                        u.GetForegroundWindow() == hwnd and area_interna(u,hwnd) == area)
            except (RuntimeError, OSError):
                return False  # Una minimizzazione durante il controllo non termina il worker.
        def pausa(durata, epoca):
            fine = time.monotonic()+durata
            while attivo.is_set() and generazione.value == epoca and time.monotonic()<fine:
                time.sleep(0.03)
        def attendi_scansione(epoca):
            inizio_attesa = time.monotonic()
            while attivo.is_set() and generazione.value == epoca:
                residuo = intervallo_scan.value - (time.monotonic()-inizio_attesa)
                if residuo <= 0:
                    break
                stato(f'Prossima scansione tra {math.ceil(residuo)} s. Intervallo modificabile nelle impostazioni.')
                time.sleep(min(0.1,residuo))
        def frame(im, epoca, candidati, secondi):
            preview = im.copy()
            draw = ImageDraw.Draw(preview)
            trovati = []
            for rett, centro, sim, conf in candidati:
                draw.rectangle(rett, outline='lime', width=2)
                trovati.append(('Scheggia', conf, sim, centro[0]+roi[0], centro[1]+roi[1]))
            preview.thumbnail((880,370), Image.Resampling.LANCZOS)
            uscita.put(('frame', epoca, preview.size, preview.tobytes(), trovati, secondi))
        esclusi = []
        ciclo = StatoScansione()
        with mss.mss() as cattura:
            while True:
                attivo.wait()
                epoca = generazione.value
                if not u.IsWindow(hwnd):
                    raise RuntimeError('Finestra chiusa: seleziona nuovamente Metin2.')
                if u.IsIconic(hwnd) or u.GetForegroundWindow()!=hwnd:
                    stato('In attesa del gioco in primo piano: ripresa automatica quando torni a Metin2.')
                    pausa(0.2, epoca)
                    continue
                area = area_interna(u,hwnd)
                if (area['width'],area['height']) != dimensioni:
                    raise RuntimeError('Finestra ridimensionata: seleziona nuovamente l’area.')
                sw,sh = mouse.size()
                if area['left']<0 or area['top']<0 or area['left']+area['width']>sw or area['top']+area['height']>sh:
                    stato('Metti Metin2 interamente sul monitor principale.')
                    pausa(1,epoca)
                    continue
                box = regione_schermo(area,roi)
                def acquisisci():
                    scatto = cattura.grab(box)
                    return Image.frombytes('RGB',scatto.size,scatto.rgb)
                im = acquisisci()
                grande = im.resize((im.width*2,im.height*2),Image.Resampling.LANCZOS)
                start = time.monotonic()
                stato(f'Analisi OCR su {motore.scelto} in corso...')
                risultati = motore.leggi(np.asarray(grande))
                secondi = time.monotonic()-start
                if not valido(epoca,area):
                    continue
                candidati = []
                for punti,testo,conf in risultati:
                    sim = somiglianza(testo)
                    if sim>=0.85 and float(conf)>=0.30:
                        rett,centro = coordinate_originali(punti,2,(0,0),im.size)
                        candidati.append((rett,centro,sim,float(conf)))
                frame(im,epoca,candidati,secondi)
                ciclo.aggiorna(len(candidati))
                stato(f'{motore.scelto} | {len(candidati)} candidati | OCR {secondi:.2f} s')
                if not candidati:
                    if ciclo.live:
                        stato('LIVE: nessuna scheggia in questa lettura; ricontrollo subito.')
                        pausa(0.2,epoca)
                    else:
                        stato('Nessuna scheggia: ritorno alla scansione con intervallo.')
                        attendi_scansione(epoca)
                    continue
                candidati, attesa = candidati_disponibili(candidati, esclusi, time.monotonic())
                if not candidati:
                    stato(f'Bersaglio in attesa: nuovo tentativo entro {math.ceil(attesa)} s. Il programma e’ attivo.')
                    pausa(min(1,max(0.1,attesa)),epoca)
                    continue
                # Un solo bersaglio per ciclo; il template resta quello confermato dall'OCR.
                rett,centro,sim,conf = max(candidati,key=lambda c:(c[2],c[3]))
                template = im.crop(rett)
                inizio = time.monotonic()
                tentativi = 0
                persi = 0
                ultimo_frame = 0
                ultimo_visto = time.monotonic()
                punto_premuto = None
                perdita_segnalata = False
                motivo_fine = 'finestra cambiata o pausa richiesta'
                stato('Raccolta live: tasto sinistro mantenuto sul bersaglio, massimo 8 s. F8 STOP.')
                try:
                    while valido(epoca,area) and time.monotonic()-inizio<8:
                        if premuto.value and punto_premuto is not None:
                            px,py = punto_premuto
                            if u.GetAncestor(u.WindowFromPoint(wintypes.POINT(px,py)),2)!=hwnd:
                                motivo_fine = 'punto premuto coperto da un’altra finestra'
                                break
                        corrente = acquisisci()
                        diagnosi = {}
                        trovato = localizza(template,corrente,centro,diagnostica=diagnosi)
                        if trovato is None:
                            if premuto.value and time.monotonic()-ultimo_visto < ritardo_rilascio.value:
                                if not perdita_segnalata:
                                    dettaglio(f'Etichetta persa: rilascio dopo {ritardo_rilascio.value:g} s senza conferma visiva.')
                                    perdita_segnalata = True
                                mouse.failSafeCheck()
                                pausa(0.03,epoca)
                                continue
                            release()
                            persi += 1
                            if persi>=3:
                                motivo_fine = diagnosi.get('motivo','bersaglio perso')
                                break
                            pausa(0.06,epoca)
                            continue
                        persi = 0
                        ultimo_visto = time.monotonic()
                        perdita_segnalata = False
                        l,t,r,b = trovato
                        centro = ((l+r)/2,(t+b)/2)
                        x,y = round(area['left']+roi[0]+centro[0]),round(area['top']+roi[1]+centro[1])
                        if not valido(epoca,area):
                            break
                        if u.GetAncestor(u.WindowFromPoint(wintypes.POINT(x,y)),2)!=hwnd:
                            motivo_fine = 'destinazione coperta da un’altra finestra: rilascio'
                            break
                        mouse.failSafeCheck()
                        sposta_mouse_verificato(u,x,y)
                        punto_premuto = (x,y)
                        if not valido(epoca,area):
                            break
                        # Aggiorna il puntatore a ogni conferma visiva senza
                        # rilasciare e ripremere durante lo stesso tratto.
                        mouse.failSafeCheck()
                        if not premuto.value:
                            punto_premuto = (x,y)
                            pressione_inizio = time.monotonic()
                            imposta_pressione(u, premuto, True)
                            tentativi += 1
                            dettaglio(f'Pressione mantenuta iniziata a ({x},{y}); puntatore in inseguimento live.')
                        if time.monotonic()-ultimo_frame>0.2:
                            frame(corrente,epoca,[(trovato,centro,sim,conf)],secondi)
                            ultimo_frame = time.monotonic()
                        fine = min(time.monotonic()+0.06, inizio+8)
                        while time.monotonic()<fine and valido(epoca,area):
                            mouse.failSafeCheck()
                            time.sleep(0.01)
                finally:
                    release()
                timeout = time.monotonic()-inizio>=8
                if timeout:
                    esclusi.append((centro,time.monotonic()+8))
                dettaglio(f'Tasto rilasciato: {tentativi} tratti di pressione mantenuta. ' +
                          ('Limite raggiunto: bersaglio in attesa 8 s, cerco gli altri.' if timeout else motivo_fine))
                stato('Ricerca automatica degli altri bersagli...' if timeout else 'Nuova lettura automatica...')
                # Il mouse e' gia' rilasciato. Nessuna attesa lunga tra gli oggetti.
                pausa(0.2,epoca)
    except Exception as errore:
        import traceback
        dettaglio(traceback.format_exc())
        uscita.put(('errore',f'{type(errore).__name__}: {errore}'))
    finally:
        if premuto.value:
            ctypes.windll.user32.mouse_event(0x0004,0,0,0,0)
            premuto.value = 0


def hotkeys(eventi, chiuso):
    """Thread dedicato ai messaggi Windows: nessun hook o input sintetico."""
    u = ctypes.WinDLL('user32', use_last_error=True)
    u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    u.RegisterHotKey.restype = wintypes.BOOL
    u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    u.UnregisterHotKey.restype = wintypes.BOOL
    u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                              wintypes.UINT, wintypes.UINT, wintypes.UINT]
    u.PeekMessageW.restype = wintypes.BOOL
    registrati = []
    try:
        for ident, tasto in ((1, 0x75), (2, 0x77)):  # F6, F8
            if not u.RegisterHotKey(None, ident, 0x4000, tasto):
                eventi.put(('hotkey_error', 'F6 o F8 gia\' occupato. Usa i pulsanti per osservare oppure chiudi '
                            'l\'altra applicazione e riapri questo programma.'))
                continue
            registrati.append(ident)
        if len(registrati) == 2:
            eventi.put(('hotkey_ok',))
        msg = wintypes.MSG()
        while not chiuso.wait(0.03):
            while u.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                eventi.put(('hotkey', int(msg.wParam)))
    finally:
        for ident in registrati:
            u.UnregisterHotKey(None, ident)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--roi', type=int, nargs=4, default=[736, 752, 1208, 420])
    parser.add_argument('--riferimento', type=Path,
                        default=Path(__file__).parent / 'cattura_20260910_144920_331585.png')
    args = parser.parse_args()
    if sys.platform != 'win32':
        raise RuntimeError('Questo programma richiede Windows 10/11.')
    from cattura_metin import api_windows, area_interna
    u = api_windows()
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk
    percorso_log = Path(__file__).resolve().parent / 'metinhub_log.txt'
    logger = prepara_registro()
    handler = logger.handlers[0]
    logger.info('Avvio MetinHub %s', VERSIONE)
    percorso_config = Path(__file__).resolve().parent / 'metinhub_settings.json'
    try:
        config = leggi_impostazioni(percorso_config)
    except (OSError, ValueError) as errore:
        logger.warning('Impostazioni ignorate: %s', errore)
        config = {}
    dimensioni = None
    if args.riferimento.exists():
        with Image.open(args.riferimento) as riferimento:
            dimensioni = riferimento.size
        regione_schermo(dict(left=0, top=0, width=dimensioni[0], height=dimensioni[1]), args.roi)
    ctx = mp.get_context('spawn')
    root = tk.Tk()
    from tema_metin import applica_tema, Navigazione, pannello, testo, Colonne
    applica_tema(root)
    root.report_callback_exception = lambda tipo, valore, tb: logger.error(
        'Errore interfaccia', exc_info=(tipo, valore, tb))
    root.title('MetinHub ' + VERSIONE_NUMERO)
    icona = Path(__file__).resolve().parent / 'MetinHub.ico'
    if icona.exists():
        root.iconbitmap(str(icona))
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MetinHub.Desktop')
    except (OSError, AttributeError):
        pass
    notebook = Navigazione(root)
    notebook.pack(fill='both', expand=True)
    raccolta = notebook.nuova_pagina()
    pagina_impostazioni = notebook.nuova_pagina()
    pagina_sistema = notebook.nuova_pagina()
    pagina_pesca = notebook.nuova_pagina()
    pesca = None
    notebook.add(raccolta, text='Schegge')
    notebook.add(pagina_pesca, text='Pesca')
    notebook.add(pagina_impostazioni, text='Impostazioni')
    notebook.add(pagina_sistema, text='Installazione')
    stato = tk.StringVar(value='Premi Scegli Metin2, poi passa al gioco entro 5 secondi.')
    tasti = tk.StringVar(value='Registrazione F6 e F8...')
    click_testo = tk.StringVar(value='Raccolta automatica attiva durante Avvia. Solo monitor principale.')
    riepilogo = tk.StringVar(value='Nessuna analisi disponibile.')
    area_testo = tk.StringVar(value=f'Area: {args.roi} | {config.get("threads_cpu",2)} thread CPU | pausa {config.get("intervallo_scan", 10):g} s'
                             if dimensioni else 'Area non ancora selezionata')
    from tema_metin import costruisci_schegge
    spazio_schegge, controllo, barra, visuale, preview = costruisci_schegge(
        raccolta, stato, tasti, click_testo, riepilogo, area_testo)
    errore_testo = tk.StringVar(value='')
    errore_label = testo(controllo, textvariable=errore_testo, foreground='#f0aaa2')
    errore_label.pack_forget()
    def mostra_errore(*_):
        if errore_testo.get(): errore_label.pack(fill='x', pady=4)
        else: errore_label.pack_forget()
    errore_testo.trace_add('write', mostra_errore)
    # Tutto lo stato GUI viene modificato soltanto dal thread principale.
    sessione = dict(hwnd=None, proc=None, canale=None, attivo=None, epoca=None,
                    arrestando=False, selezionando=False, selezione_id=0, foto=None, dialogo=None,
                    click_richiesto=None, click_pendente=0, ultimo_click=0, pronto=False,
                    ultimo_errore=None, riavvio_richiesto=False)
    premuto = ctx.Value('i', 0, lock=False)
    profilo_cpu = tk.StringVar(value='Leggera - 1 thread' if config.get('threads_cpu',2)==1 else 'Normale - 2 thread')
    url_aggiornamenti = tk.StringVar(value=config.get('url_aggiornamenti',''))
    def numero_threads():
        return 1 if profilo_cpu.get().startswith('Leggera') else 2
    motore_scelta = tk.StringVar(value=config.get('motore', 'Auto'))
    intervallo_scan = ctx.Value('d', config.get('intervallo_scan', 10.0))
    intervallo_testo = tk.StringVar(value=f'{intervallo_scan.value:g}')
    ritardo_rilascio = ctx.Value('d', config.get('ritardo_rilascio', 0.2))
    rilascio_testo = tk.StringVar(value=f'{ritardo_rilascio.value:g}')
    from tema_metin import ColonneImpostazioni
    spazio_impostazioni = ColonneImpostazioni(pagina_impostazioni)
    impostazioni = pannello(spazio_impostazioni.sinistra, 'Tempi di ricerca', 'Pausa senza schegge. L’inseguimento resta live.')
    impostazioni.configure(padding=(10,6))
    testo(impostazioni, 'Pausa tra le scansioni (secondi)', role='label')
    ttk.Spinbox(impostazioni, from_=1, to=3600, increment=1, width=9, textvariable=intervallo_testo).pack(anchor='w', pady=(2,4))
    def applica_impostazioni():
        try:
            valore = intervallo_valido(intervallo_testo.get())
            rilascio = rilascio_valido(rilascio_testo.get())
            salva_impostazioni(percorso_config, valore, motore_scelta.get(), rilascio, numero_threads(), url_aggiornamenti.get())
            intervallo_scan.value = valore
            ritardo_rilascio.value = rilascio
            rilascio_testo.set(f'{rilascio:g}')
            intervallo_testo.set(f'{valore:g}')
            area_testo.set(f'Area interna: {args.roi} | {numero_threads()} thread CPU | pausa scansioni {valore:g} s')
            stato.set(f'Intervallo salvato: {valore:g} s. Applicato anche alla scansione attiva.')
            logger.info('Intervallo salvato: %s secondi', valore)
        except (OSError, ValueError) as errore:
            from tkinter import messagebox
            messagebox.showerror('Impostazioni', str(errore), parent=root)
    rilascio_barra = pannello(spazio_impostazioni.sinistra, 'Inseguimento del bersaglio',
                              'Attesa prima di rilasciare il mouse quando l’etichetta scompare.')
    rilascio_barra.configure(padding=(10,6))
    testo(rilascio_barra, 'Ritardo di rilascio (secondi)', role='label')
    ttk.Spinbox(rilascio_barra, from_=0.1, to=1.5, increment=0.1, width=9,
                textvariable=rilascio_testo).pack(anchor='w', pady=(2,4))
    prestazioni = pannello(spazio_impostazioni.destra, 'Prestazioni', 'Motore e thread si applicano dopo STOP e Avvia.')
    prestazioni.configure(padding=(10,6))
    testo(prestazioni, 'Motore OCR', role='label')
    ttk.Combobox(prestazioni, textvariable=motore_scelta, values=['Auto','CPU','GPU'], state='readonly', width=25).pack(fill='x', pady=(2,8))
    testo(prestazioni, 'Profilo CPU', role='label')
    ttk.Combobox(prestazioni, textvariable=profilo_cpu, values=['Normale - 2 thread','Leggera - 1 thread'],
                 state='readonly', width=25).pack(fill='x', pady=(2,4))
    testo(prestazioni, 'Il profilo Leggera riduce il lavoro parallelo; il riconoscimento può richiedere più tempo.', muted=True)
    eventi = queue.Queue()
    chiuso = threading.Event()


    def apri_log():
        from tkinter import messagebox
        if percorso_log.exists():
            os.startfile(str(percorso_log))
        else:
            messagebox.showinfo('Diagnostica', 'Nessun rapporto salvato. Puoi usare Salva diagnosi adesso.', parent=root)
    salvataggio = pannello(pagina_impostazioni, 'Applica la configurazione',
                          'Salva tempi, motore, profilo CPU e canale aggiornamenti.')
    salvataggio.configure(padding=(10,4))
    ttk.Button(salvataggio, text='Salva impostazioni', style='Primary.TButton', command=applica_impostazioni).pack(anchor='w', pady=(4,2))

    diagnostica = pannello(pagina_impostazioni, 'Diagnostica', 'Il registro viene scritto soltanto su errore o su tua richiesta.')
    diagnostica.configure(padding=(10,4))
    ttk.Button(diagnostica, text='Apri registro diagnostico', style='Secondary.TButton', command=apri_log).pack(anchor='w', pady=3)
    def salva_diagnosi():
        handler.salva('Diagnosi richiesta manualmente dall’utente')
        apri_log()
    ttk.Button(diagnostica, text='Salva diagnosi adesso', style='Secondary.TButton', command=salva_diagnosi).pack(anchor='w', pady=3)

    def ferma(motivo='STOP richiesto; il riavvio richiede Avvia.'):
        if pesca is not None:
            pesca.stop()
        sessione['riavvio_richiesto'] = False
        logger.info(motivo)
        sessione['click_pendente'] = 0
        sessione['pronto'] = False
        if sessione['click_richiesto'] is not None:
            sessione['click_richiesto'].value = 0
        click_testo.set('Click disattivato; nessuna richiesta pendente.')
        if sessione['dialogo'] is not None:
            sessione['dialogo'].destroy()
            sessione['dialogo'] = None
        sessione['selezione_id'] += 1
        sessione['selezionando'] = False
        if sessione['attivo']:
            sessione['attivo'].clear()
        p = sessione['proc']
        if p is not None:
            if p.is_alive():
                p.terminate()
            p.join(timeout=0.3)
            sessione['arrestando'] = True
        if premuto.value:
            u.mouse_event(0x0004,0,0,0,0)
            premuto.value = 0
        stato.set('STOP. Premi Avvia per ripartire sulla finestra scelta.')
        riepilogo.set('Osservazione ferma; l\'immagine eventualmente visibile e\' precedente.')

    def avvia_pausa():
        if pesca is not None:
            pesca.stop()
        if sessione['selezionando']:
            return
        if sessione['arrestando']:
            sessione['riavvio_richiesto'] = True
            stato.set('Riavvio richiesto: attendo la chiusura del processo precedente...')
            return
        if sessione['hwnd'] is None:
            stato.set('Prima premi Scegli Metin2.')
            return
        if sessione['proc'] is None:
            sessione['ultimo_errore'] = None
            errore_testo.set('')
            logger.info('Avvio raccolta: motore=%s ROI=%s dimensioni=%s', motore_scelta.get(), args.roi, dimensioni)
            sessione['canale'] = ctx.Queue()
            sessione['attivo'] = ctx.Event()
            sessione['epoca'] = ctx.Value('i', 0)
            sessione['click_richiesto'] = ctx.Value('d', 0)
            sessione['pronto'] = False
            sessione['attivo'].set()
            p = ctx.Process(target=worker, args=(sessione['hwnd'], dimensioni, tuple(args.roi),
                            sessione['attivo'], sessione['epoca'], sessione['canale'],
                            sessione['click_richiesto'], motore_scelta.get(), premuto, intervallo_scan, ritardo_rilascio, numero_threads()), daemon=True)
            sessione['proc'] = p
            p.start()
            click_testo.set('Raccolta automatica: torna al gioco. F8 o STOP per fermare.')
            stato.set('Avvio OCR...')
        elif sessione['attivo'].is_set():
            logger.info('Pausa manuale richiesta.')
            sessione['attivo'].clear()
            sessione['click_richiesto'].value = 0
            sessione['click_pendente'] = 0
            click_testo.set('In pausa: eventuale click pendente annullato.')
            with sessione['epoca'].get_lock():
                sessione['epoca'].value += 1
            stato.set('In pausa. Una lettura in corso puo\' finire; F8 interrompe anche il calcolo.')
            riepilogo.set('In pausa: anteprima precedente. F6 per riprendere.')
        else:
            logger.info('Ripresa manuale richiesta.')
            sessione['attivo'].set()
            click_testo.set('Raccolta automatica attiva quando Metin2 e’ in primo piano.')
            stato.set('Ripresa: porta Metin2 in primo piano.')

    def scegli(nuova_area=False):
        ferma()
        sessione['hwnd'] = None
        sessione['selezionando'] = True
        codice = sessione['selezione_id']
        def conto(n):
            if codice != sessione['selezione_id']:
                return
            if n:
                testo = f'Porta Metin2 in primo piano: selezione tra {n} secondi.'
                stato.set(testo)
                print(testo, flush=True)
                root.after(1000, lambda: conto(n-1))
                return
            try:
                hwnd = u.GetForegroundWindow()
                titolo = ctypes.create_unicode_buffer(u.GetWindowTextLengthW(hwnd)+1)
                u.GetWindowTextW(hwnd, titolo, len(titolo))
                if 'metin2' not in titolo.value.casefold():
                    raise RuntimeError('La finestra attiva non e\' Metin2. Premi di nuovo Scegli Metin2.')
                area = area_interna(u, hwnd)
                if nuova_area:
                    import mss
                    with mss.mss() as cattura:
                        if not any(area['left'] >= m['left'] and area['top'] >= m['top']
                                   and area['left'] + area['width'] <= m['left'] + m['width']
                                   and area['top'] + area['height'] <= m['top'] + m['height']
                                   for m in cattura.monitors[1:]):
                            raise RuntimeError('Metti tutta la finestra dentro un solo monitor e riprova.')
                        scatto = cattura.grab(area)
                    if area_interna(u, hwnd) != area or u.GetForegroundWindow() != hwnd:
                        raise RuntimeError('La finestra si e\' spostata durante la cattura. Riprova.')
                    immagine = Image.frombytes('RGB', scatto.size, scatto.rgb)

                    def applica(roi):
                        nonlocal dimensioni
                        sessione['dialogo'] = None
                        if codice != sessione['selezione_id']:
                            return
                        sessione['selezionando'] = False
                        if roi is None:
                            stato.set('Selezione annullata. Premi Scegli Metin2 o Seleziona area.')
                            return
                        args.roi = list(roi)
                        dimensioni = immagine.size
                        sessione['hwnd'] = hwnd
                        sessione['foto'] = None
                        preview.configure(image='', text='Nuova area impostata. In attesa della prima analisi.')
                        area_testo.set(f'Area interna: {args.roi} | {numero_threads()} thread CPU | pausa scansioni {intervallo_scan.value:g} s')
                        riepilogo.set('Nessuna analisi della nuova area.')
                        stato.set('Area impostata. Torna al gioco e premi F6 per avviare.')
                        print(f'Nuova area interna: {args.roi}. Dimensioni finestra: {dimensioni}', flush=True)
                    stato.set('Disegna il rettangolo nella finestra di selezione.')
                    sessione['dialogo'] = selettore_area(root, immagine, applica)
                    return
                if dimensioni is None:
                    raise RuntimeError('Premi Seleziona area per impostare il primo ritaglio.')
                if (area['width'], area['height']) != dimensioni:
                    raise RuntimeError(f'Dimensioni diverse dal riferimento {dimensioni}: '
                                       'premi Seleziona area per aggiornare il ritaglio.')
                regione_schermo(area, args.roi)
                sessione['hwnd'] = hwnd
                stato.set('Metin2 selezionato. Premi F6 per avviare.')
                print('Metin2 selezionato. Premi F6 per avviare.', flush=True)
            except Exception as errore:
                stato.set(str(errore))
                print(errore, flush=True)
            sessione['selezionando'] = False
        conto(5)

    def aggiorna():
        while True:
            try:
                evento = eventi.get_nowait()
            except queue.Empty:
                break
            if evento[0] == 'hotkey':
                if evento[1] == 1:
                    if pesca is not None and notebook.select()==str(pagina_pesca):
                        pesca.stop() if pesca.proc else pesca.start()
                    else:
                        avvia_pausa()
                elif evento[1] == 2:
                    ferma()
            elif evento[0] == 'hotkey_ok':
                tasti.set('F6: avvia / pausa | F8: STOP | Puoi usare i pulsanti')
            else:
                tasti.set(evento[1])
        p = sessione['proc']
        if p is not None and not sessione['arrestando']:
            while True:
                try:
                    evento = sessione['canale'].get_nowait()
                except (queue.Empty, EOFError, OSError):
                    break
                if evento[0] == 'errore':
                    errore = evento[1]
                    ferma('Arresto per errore del processo; nessuno STOP manuale richiesto.')
                    sessione['ultimo_errore'] = errore
                    errore_testo.set('ARRESTO PER ERRORE: ' + errore + ' | Vedi metinhub_log.txt; Avvia per riprovare.')
                    logger.error(errore)
                    stato.set(errore)
                    print(errore, flush=True)
                    break
                if evento[0] == 'dettaglio':
                    click_testo.set(evento[1])
                    logger.info(evento[1])
                    continue
                if evento[0] == 'click_esito':
                    if evento[1] == sessione['click_pendente']:
                        sessione['click_pendente'] = 0
                        click_testo.set(evento[2])
                        print(evento[2], flush=True)
                    continue
                if not sessione['attivo'].is_set():
                    continue
                if evento[0] == 'stato':
                    stato.set(evento[1])
                    logger.info(evento[1])
                elif evento[0] == 'frame' and evento[1] == sessione['epoca'].value:
                    sessione['pronto'] = True
                    _, _, size, dati, trovati, secondi = evento
                    immagine = Image.frombytes('RGB', size, dati)
                    immagine.thumbnail((max(160, visuale.winfo_width()-55), 370))
                    sessione['foto'] = ImageTk.PhotoImage(immagine)
                    preview.configure(image=sessione['foto'], text='', padding=8)
                    righe = [f'Ultima analisi: {len(trovati)} candidati | OCR {secondi:.2f} s']
                    for testo, conf, sim, x, y in trovati[:8]:
                        righe.append(f'Centro interno ({x:.1f}, {y:.1f}) | OCR {conf:.2f} | somiglianza {sim:.2f}')
                    if len(trovati) > 8:
                        righe.append(f'Altri {len(trovati)-8} candidati nell\'anteprima.')
                    riepilogo.set('\n'.join(righe))
                    print(righe[0], flush=True)
        if p is not None and not p.is_alive():
            p.join(timeout=0)
            if premuto.value:
                u.mouse_event(0x0004,0,0,0,0)
                premuto.value = 0
            if not sessione['arrestando']:
                messaggio = f'Processo OCR terminato (codice {p.exitcode}). Premi Avvia per riprovare.'
                if not sessione['ultimo_errore']:
                    sessione['ultimo_errore'] = messaggio
                    errore_testo.set(messaggio)
                stato.set(sessione['ultimo_errore'])
                logger.error(sessione['ultimo_errore'])
            sessione['canale'].cancel_join_thread()
            sessione['canale'].close()
            sessione.update(proc=None, canale=None, arrestando=False, attivo=None, epoca=None,
                            click_richiesto=None, click_pendente=0, pronto=False)
            if sessione['riavvio_richiesto']:
                sessione['riavvio_richiesto'] = False
                avvia_pausa()
        root.after(80, aggiorna)

    def chiudi():
        chiuso.set()
        ferma()
        root.destroy()

    ttk.Button(barra, text='Scegli finestra', style='Secondary.TButton', command=scegli).grid(row=0, column=0, sticky='ew', pady=4)
    ttk.Button(barra, text='Seleziona area', style='Secondary.TButton', command=lambda: scegli(True)).grid(row=1, column=0, sticky='ew', pady=4)
    ttk.Button(barra, text='Avvia / Pausa  ·  F6', style='Primary.TButton', command=avvia_pausa).grid(row=2, column=0, sticky='ew', pady=(12,4))
    ttk.Button(barra, text='Arresta  ·  F8', style='Stop.TButton', command=ferma).grid(row=3, column=0, sticky='ew', pady=4)
    try:
        from interfaccia_sistema import aggiungi_sistema
        aggiungi_sistema(pagina_sistema, root, VERSIONE_NUMERO, url_aggiornamenti, chiudi)
    except ImportError:
        ttk.Label(pagina_sistema, text='Per la manutenzione installa tutti i file del pacchetto MetinHub.', padding=20).pack()
    from pesca_debug import SchedaPesca
    pesca = SchedaPesca(pagina_pesca, root, ferma)
    root.protocol('WM_DELETE_WINDOW', chiudi)
    t = threading.Thread(target=hotkeys, args=(eventi, chiuso), daemon=True)
    t.start()
    root.after(80, aggiorna)
    try:
        root.mainloop()
    finally:
        if pesca is not None:
            pesca.stop()
        chiuso.set()
        p = sessione['proc']
        if p is not None:
            if p.is_alive():
                p.terminate()
            p.join(timeout=1)
        if premuto.value:
            u.mouse_event(0x0004,0,0,0,0)
            premuto.value = 0
        t.join(timeout=0.2)


if __name__ == '__main__':
    mp.freeze_support()
    logger = prepara_registro()
    threading.excepthook = lambda args: logger.error('Errore thread', exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as errore:
        logger.exception('Chiusura imprevista di MetinHub')
        print(f'Errore: {errore}')
        raise SystemExit(1)
