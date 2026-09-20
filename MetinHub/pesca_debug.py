"""Scheda Pesca: processo dedicato, osservazione e test di un click o tre colpi di una singola pescata."""
import multiprocessing as mp
import queue
import time
import logging
from pathlib import Path


def processo_pesca(hwnd, output, stop, save, real=False, held=None):
    import os
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[name]='1'
    try:
        import cv2, numpy as np, mss, threading
        from cattura_metin import api_windows, area_interna
        from pesca_core import VisionePesca, CicloPesca, leggi_colpi
        cv2.setNumThreads(1)
        base=Path(__file__).resolve().parent
        vision=VisionePesca(base/'pesca_riferimento.png');cycle=CicloPesca()
        u=api_windows()
        from pesca_input import MouseWindows, click_singolo
        from osserva_metin import sposta_mouse_verificato
        mouse_api=MouseWindows(u)
        budget=int(real)
        if budget not in (0,1,3):raise ValueError("Numero di click non valido")
        available=budget==1;deadline=time.monotonic()+30;seen_foreground=False
        new_cast=True;cast_number=0
        real_total=0;real_point=None;real_baseline=None;real_time=None
        real_status=('PESCA CONTINUA: attendo una nuova pescata a 0/3' if budget==3 else 'ARMATO: un click reale') if real else 'Solo simulazione'
        window=None;last_search=0;last_save=0;last_ocr=0
        generation=0;counter=None;previous=None;confirmations=0;count_time=0
        visual_previous=None;visual_confirm=0;last_visual=0;last_simulated_at=None
        requests=queue.Queue(maxsize=1);answers=queue.Queue(maxsize=2)
        def ocr_loop():
            try:
                import torch,easyocr
                torch.set_num_threads(1)
                reader=easyocr.Reader(['it','en'],gpu=False,detector=False,download_enabled=False,verbose=False)
                while not stop.is_set():
                    try:gen,stamp,img=requests.get(timeout=0.2)
                    except queue.Empty:continue
                    rows=reader.recognize(img,detail=1,allowlist='0123/',paragraph=False)
                    try:answers.put_nowait((gen,stamp,leggi_colpi(rows),None))
                    except queue.Full:pass
            except Exception as error:
                try:answers.put_nowait((-1,0,None,str(error)))
                except queue.Full:pass
        ocr_started=False
        ocr_status='Contatore visivo pronto; OCR di riserva';ocr_error=None;folder=None;saved=0
        started=time.monotonic();frames=0;last_ui=0
        def send(data):
            try:output.put_nowait(data)
            except queue.Full:pass
        with mss.mss() as camera:
            while not stop.is_set():
                tick=time.monotonic()
                if not u.IsWindow(hwnd):raise RuntimeError('Finestra gioco chiusa.')
                if (available or real_time is not None) and tick>deadline:
                    available=False;real_time=None;real_status=f'Tempo scaduto: {real_total} click inviati, pescata fermata'
                if u.IsIconic(hwnd) or u.GetForegroundWindow()!=hwnd:
                    if real_time is not None:
                        real_time=None;real_status='Click inviato; verifica interrotta dal cambio finestra'
                    if available and seen_foreground:
                        available=False;real_status='Disarmato: gioco non piu in primo piano'
                    window=None;cycle.reset();generation+=1;counter=None;previous=None;confirmations=0
                    send({'status':'In attesa del gioco in primo piano | '+real_status});stop.wait(0.2);continue
                seen_foreground=True
                area=area_interna(u,hwnd)
                def grab(box):return np.asarray(camera.grab(box))[:,:,:3].copy()
                if window is None:
                    if tick-last_search<0.5:stop.wait(0.03);continue
                    last_search=tick;whole=grab(area);window=vision.find_window(whole)
                    if window is None:
                        send({'status':'ATTESA FINESTRA PESCA | '+real_status});continue
                    generation+=1;cycle.reset();counter=None;previous=None;confirmations=0
                    new_cast=True
                    started=tick;frames=0
                    visual_previous=None;visual_confirm=0;last_visual=0;last_simulated_at=None
                x,y,w,h=window
                if x+w>area['width'] or y+h>area['height']:
                    available=False;real_time=None;real_status='Area cambiata: pescata fermata'
                    window=None;continue
                crop=grab(dict(left=area['left']+x,top=area['top']+y,width=w,height=h))
                result=vision.analyse(crop)
                if result is None:
                    if real_time is not None:
                        real_time=None;real_status='Click inviato; finestra pesca scomparsa, esito non verificabile'
                    if available:
                        available=False;real_status='Disarmato: finestra pesca persa'
                    window=None;cycle.reset();generation+=1;counter=None;continue
                raw=result['counter_value']
                visual_confirm=visual_confirm+1 if raw is not None and raw==visual_previous else (1 if raw is not None else 0)
                visual_previous=raw
                if visual_confirm>=2:
                    if budget==3 and raw==0 and (new_cast or counter in (1,2,3)):
                        # Solo un nuovo 0/3 confermato avvia il timer della pescata.
                        # Uno 0/3 che persiste dopo il timeout non rinnova il timer.
                        available=True;deadline=tick+30;new_cast=False;cast_number+=1
                        real_total=0;real_time=None;real_baseline=None;real_point=None
                        cycle.reset();counter=None;last_simulated_at=None
                        generation+=1;previous=None;confirmations=0
                        real_status=f'Pescata {cast_number}: attiva fino a 3/3'
                    elif raw==0 and counter in (1,2,3):
                        cycle.reset();counter=None;last_simulated_at=None
                        if real:
                            available=False;real_time=None
                            real_status='Test singolo: riarmare manualmente'
                    if counter is None or raw>=counter:
                        counter=raw;count_time=tick;last_visual=tick
                        ocr_status='Contatore visivo live (2 conferme)'
                while True:
                    try:gen,stamp,value,error=answers.get_nowait()
                    except queue.Empty:break
                    if error:
                        ocr_status='OCR non disponibile: '+error;ocr_error=ocr_status
                    elif gen==generation and tick-stamp<1 and tick-last_visual>1:
                        ocr_status='OCR contatore attivo'
                        if value is not None:
                            confirmations=confirmations+1 if value==previous else 1;previous=value
                            if confirmations>=2:
                                if budget!=3 and value==0 and counter==3:cycle.reset();counter=None
                                if counter is None or value>=counter:counter=value;count_time=tick
                if raw is None and tick-last_visual>1 and tick-last_ocr>=0.5:
                    if not ocr_started:
                        threading.Thread(target=ocr_loop,daemon=True).start();ocr_started=True
                        ocr_status='Caricamento OCR di riserva: cifra visiva incerta'
                    last_ocr=tick
                    # Solo il contatore: riconoscimento separato dal tracking live.
                    digits=result['image'][40:55,241:272]
                    try:requests.put_nowait((generation,tick,cv2.resize(digits,None,fx=4,fy=4)))
                    except queue.Full:pass
                observed=counter if tick-count_time<3 else None
                point=result['point']
                local=None if point is None else (round(x+point[0]*w/285),round(y+point[1]*h/258))
                # Conferma prima di aggiornare il ciclo: evita di perdere la
                # transizione RED se la lettura del contatore arriva dopo il cooldown.
                if real and observed==3:
                    available=False;real_time=None;real_status=('COMPLETATO 3/3: lancia la prossima canna, ripresa automatica' if budget==3 else 'COMPLETATO 3/3')
                elif real_total and real_time is not None:
                    if observed is not None and observed>real_baseline:
                        real_time=None
                        if budget==3 and tick<deadline:
                            available=True
                            real_status=f'Colpo confermato: {observed}/3. Attendo cooldown e nuovo rosso'
                        else:
                            available=False;real_status=f'Test terminato: {real_total} click, contatore {observed}/3'
                    elif tick-real_time>3:
                        real_time=None
                        available=budget==3 and tick<deadline
                        real_status=('Colpo non confermato: attendo nuovo rosso per riprovare' if available else 'Test singolo terminato: colpo non confermato')
                simulated=cycle.update(tick,True,result['color'],local,observed)
                if available and simulated is not None:
                    # Blocca durante l'input; il ciclo impedisce duplicati sullo stesso rosso.
                    available=False
                    def target_fresco():
                        if stop.is_set() or time.monotonic()>=deadline or u.GetForegroundWindow()!=hwnd or u.IsIconic(hwnd):return None
                        if area_interna(u,hwnd)!=area:return None
                        fresh=vision.analyse(grab(dict(left=area['left']+x,top=area['top']+y,width=w,height=h)))
                        if fresh is None or fresh['color']!='RED' or fresh['point'] is None:return None
                        if fresh['counter_value'] not in (0,1,2) or fresh['counter_value']!=observed:return None
                        fx,fy=fresh['point']
                        return (round(area['left']+x+fx*w/285),round(area['top']+y+fy*h/258)),fresh['counter_value']
                    sent,real_status,real_point,real_baseline=click_singolo(mouse_api,hwnd,stop,held,target_fresco,
                        lambda px,py:sposta_mouse_verificato(u,px,py),stop.wait)
                    if sent:
                        real_total+=1;real_time=time.monotonic()
                        available=budget==3 and real_time<deadline
                    else:
                        # Nessun input: non aspettare un successo impossibile.
                        # La ripresa richiede comunque NORMAL, cooldown e nuovo RED.
                        available=not stop.is_set() and time.monotonic()<deadline
                if simulated is not None:last_simulated_at=tick
                frames+=1
                if save and tick-last_save>=0.5 and saved<300:
                    if folder is None:
                        from datetime import datetime
                        folder=base/'debug_pesca'/datetime.now().strftime('%Y%m%d_%H%M%S_%f');folder.mkdir(parents=True)
                    name=f'frame_{saved:04d}'
                    if not cv2.imwrite(str(folder/(name+'.png')),crop):raise OSError('Salvataggio frame non riuscito')
                    import json
                    (folder/(name+'.json')).write_text(json.dumps(dict(cast_number=cast_number,real_mode='continuous_3_hits' if budget==3 else 'single_click' if budget else 'simulation',real_click_budget=None if budget==3 else budget,real_clicks_sent=real_total,real_status=real_status,real_point_desktop=real_point,elapsed_s=round(tick-started,3),simulated_total=cycle.simulated,last_simulated_point=cycle.last_point,last_simulated_age_s=None if last_simulated_at is None else round(tick-last_simulated_at,3),counter_raw=raw,counter_score=result['counter_score'],counter_age_s=None if counter is None else round(tick-count_time,3),color=result['color'],confidence=result['confidence'],point=local,observed_hits=observed,simulated_click=simulated,state=cycle.state,fish_reason=result['reason'],fish_box=result['fish_box']),ensure_ascii=False),encoding='utf-8')
                    saved+=1;last_save=tick
                if tick-last_ui>=0.1:
                    last_ui=tick;image=result['image'].copy()
                    if point:
                        px,py=map(round,point)
                        bx,by,bw,bh=result['fish_box']
                        cv2.rectangle(image,(bx,by),(bx+bw,by+bh),(0,255,0),1)
                    if cycle.last_point:
                        px=round((cycle.last_point[0]-x)*285/w);py=round((cycle.last_point[1]-y)*258/h)
                        cv2.drawMarker(image,(px,py),(255,0,255),cv2.MARKER_CROSS,12,1)
                    send(dict(real_total=real_total,real_status=real_status,status=cycle.state,color=result['color'],confidence=result['confidence'],point=local,
                              hits=observed,simulated=cycle.simulated,fps=frames/max(0.01,tick-started),
                              saved=saved,folder=str(folder or ''),ocr=ocr_status,reason=result['reason'],ocr_error=ocr_error,image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB).tobytes()))
                stop.wait(max(0,1/30-(time.monotonic()-tick)))
    except Exception:
        import traceback
        try:output.put({'error':traceback.format_exc()},timeout=0.2)
        except queue.Full:pass
    finally:
        if held is not None and held.value:
            import ctypes
            ctypes.windll.user32.mouse_event(0x0004,0,0,0,0)
            held.value=0


class SchedaPesca:
    def __init__(self,parent,root,before_start):
        import tkinter as tk
        from tkinter import ttk
        self.root=root;self.before_start=before_start;self.proc=None;self.hwnd=None;self.selection=0
        self.ctx=mp.get_context('spawn');self.status=tk.StringVar(value='Test senza input: scegli il gioco, poi avvia e pesca manualmente.')
        self.save=tk.BooleanVar(value=False)
        from tema_metin import pannello, testo, Colonne, AzioniSessione, AnteprimaPesca, FONT, stato_evidenza, indicatori_pesca
        controllo=pannello(parent, 'Sessione di pesca', 'Lancia la canna manualmente. La modalità continua si riattiva a ogni nuova pescata.')
        stato_evidenza(controllo,self.status)
        bar=AzioniSessione(controllo)
        bar.columnconfigure(0,weight=1)
        ttk.Button(bar,text='Scegli finestra',style='Secondary.TButton',command=self.choose).grid(row=0,column=0,sticky='ew',pady=5)
        ttk.Button(bar,text='Arresta  ·  F8',style='Stop.TButton',command=self.stop).grid(row=2,column=0,sticky='ew',pady=5)
        ttk.Button(bar,text='Avvia pesca continua',style='Primary.TButton',command=lambda:self.arm(3)).grid(row=1,column=0,sticky='ew',pady=5)
        spazio=Colonne(parent)
        tracking=pannello(spazio.sinistra,'Anteprima del minigioco','Verde: pesce riconosciuto. Viola: ultimo punto di click simulato.')
        self.metriche=tk.StringVar(value='Colpi — / 3    ·    Cerchio —    ·    Tracking — FPS')
        indicatori_pesca(tracking,self.metriche)
        self.preview=AnteprimaPesca(tracking)
        self.preview.configure(text='In attesa della finestra di pesca')
        self.preview.pack(fill='x',pady=(4,6))
        test=pannello(spazio.destra,'Prove e diagnostica','Usa la simulazione per verificare il riconoscimento senza inviare click.')
        test.configure(padding=(10,6))
        testbar=ttk.Frame(test,style='Card.TFrame');testbar.pack(fill='x',pady=4)
        ttk.Button(testbar,text='Simula senza click',width=22,style='Secondary.TButton',command=self.start).pack(anchor='w',pady=3)
        ttk.Button(testbar,text='Prova un click',width=22,style='Secondary.TButton',command=self.arm).pack(anchor='w',pady=3)
        ttk.Checkbutton(test,text='Salva immagini della prova',variable=self.save).pack(anchor='w',pady=8)
        testo(test,'Si applica al prossimo avvio: 2 immagini al secondo, massimo 300, nella cartella debug_pesca.',role='technical')
        self.dettagli=tk.StringVar(value='Nessuna lettura disponibile.')
        dettagli_label=testo(test,textvariable=self.dettagli,role='technical')
        dettagli_label.pack_forget()
        def dettagli_visibili():
            if dettagli_label.winfo_manager():
                dettagli_label.pack_forget();dettagli_button.configure(text='Mostra dettagli tecnici')
            else:
                dettagli_label.pack(fill='x',pady=8);dettagli_button.configure(text='Nascondi dettagli tecnici')
        dettagli_button=ttk.Button(test,text='Mostra dettagli tecnici',style='Ghost.TButton',command=dettagli_visibili)
        dettagli_button.pack(anchor='w',pady=6)
        self.root.after(100,self.poll)
    def choose(self):
        self.before_start();self.stop();self.selection+=1;token=self.selection
        def countdown(n):
            if token!=self.selection:return
            if n:
                self.status.set(f'Porta il gioco in primo piano: {n} secondi');self.root.after(1000,lambda:countdown(n-1));return
            try:
                from cattura_metin import api_windows
                self.hwnd=api_windows().GetForegroundWindow()
                self.status.set('Gioco selezionato. Premi Avvia test, torna al gioco e lancia la canna manualmente.')
            except Exception as e:self.status.set(str(e))
        countdown(5)
    def arm(self,limit=1):
        self.stop()
        self.start(real=limit)
    def start(self,real=False):
        if self.proc:return
        if not self.hwnd:self.status.set('Prima scegli il gioco.');return
        self.before_start()
        self.output=self.ctx.Queue(maxsize=2);self.stop_event=self.ctx.Event();self.held=self.ctx.Value('i',0,lock=False)
        self.proc=self.ctx.Process(target=processo_pesca,args=(self.hwnd,self.output,self.stop_event,self.save.get(),real,self.held),daemon=True)
        self.proc.start();self.status.set(('PESCA CONTINUA: torna al gioco e lancia la canna. Ripresa automatica a ogni nuovo 0/3.' if int(real)==3 else 'ARMATO: torna al gioco. Un click reale, entro 30 secondi.') if real else 'Avvio simulazione: nessun click reale.');self.error=False;self.ocr_error_logged=False
    def stop(self):
        self.selection+=1
        if self.proc:
            self.stop_event.set();self.proc.join(timeout=0.15)
            if self.proc.is_alive():self.proc.terminate();self.proc.join(timeout=0.3)
            self.release()
            self.output.cancel_join_thread();self.output.close();self.proc=None
        self.status.set('Test pesca fermato.')
    def release(self):
        if hasattr(self,'held') and self.held.value:
            import ctypes
            ctypes.windll.user32.mouse_event(0x0004,0,0,0,0);self.held.value=0
    def poll(self):
        if self.proc:
            try:
                while True:
                    item=self.output.get_nowait()
                    if 'error' in item:
                        logging.getLogger('metinhub').error(item['error']);self.error=True
                        self.status.set('Errore pesca: vedi metinhub_log.txt');continue
                    if 'image' not in item:self.status.set(item['status']);continue
                    if item.get('ocr_error') and not self.ocr_error_logged:
                        logging.getLogger('metinhub').error(item['ocr_error']);self.ocr_error_logged=True
                    from PIL import Image,ImageTk
                    im=Image.frombytes('RGB',(285,258),item.pop('image'))
                    larghezza=max(200,min(480,self.preview.winfo_width()-30))
                    self.photo=ImageTk.PhotoImage(im.resize((larghezza,round(larghezza*258/285))))
                    self.preview.configure(image=self.photo,text='',padding=8)
                    hits='?/3' if item['hits'] is None else str(item['hits'])+'/3'
                    self.status.set(item['real_status'])
                    self.metriche.set(f"Colpi {hits}    ·    Cerchio {item['color']}    ·    {item['fps']:.1f} FPS")
                    self.dettagli.set(f"{item['real_status']} | Click reali: {item['real_total']}\n{item['status']}\nCerchio: {item['color']} | Pesce: {item['point']} | Qualita sagoma: {item['confidence']:.2f} (non probabilita)\n{item['reason']}\nColpi letti: {hits} | Click simulati: {item['simulated']} | FPS medi: {item['fps']:.1f}\nFrame salvati: {item['saved']} | {item['folder']}\n{item['ocr']}")
            except (queue.Empty,EOFError,OSError):pass
            if not self.proc.is_alive():
                if not self.error:
                    logging.getLogger('metinhub').error('Processo Pesca terminato inaspettatamente: %s',self.proc.exitcode)
                    self.status.set('Processo Pesca terminato: vedi registro.')
                self.release()
                self.output.cancel_join_thread();self.output.close();self.proc.join();self.proc=None
        self.root.after(100,self.poll)
