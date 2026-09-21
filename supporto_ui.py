"""Supporto page: calibration, persistent settings and dry-run telemetry."""
from datetime import datetime
import ctypes
import logging
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from configurazione import leggi_configurazione, aggiorna_configurazione
from supporto_core import KEYS, defaults, validate, calibrate
from supporto_worker import run_support
from tema_metin import pannello, testo, Colonne, COLORI, FONT, stato_evidenza


class SchedaSupporto:
    def __init__(self,parent,root,config_path,select_area):
        self.root=root;self.path=Path(config_path);self.select_area=select_area
        self.hwnd=None;self.thread=None;self.stop_event=None;self.dialog=None
        self.selection=0;self.closed=False;self.image_stamp=None
        self.logger=logging.getLogger('metinhub')
        try:
            self.saved=validate(leggi_configurazione(self.path).get('supporto',{}))
            load_error=''
        except (ValueError,OSError) as e:
            self.saved=validate({});load_error='Impostazioni Supporto non caricate: '+str(e)
        self.status=tk.StringVar(value=load_error or 'FERMO — Modalità test attiva')
        self.values={}
        self.skills=[]
        self.debug=tk.BooleanVar(value=True);self.dry=tk.BooleanVar(value=True)
        self.snapshots=queue.Queue(maxsize=1);self.events=queue.Queue(maxsize=200)
        panel=pannello(parent,'Sessione Supporto','Monitor HP e timer indipendenti. F8 arresta tutti i moduli.')
        stato_evidenza(panel,self.status)
        bar=ttk.Frame(panel,style='Card.TFrame');bar.pack(fill='x')
        for label,command,style in (
            ('Scegli Metin2 (5 s)',self.choose,'Secondary.TButton'),
            ('Calibra HP (5 s)',lambda:self.choose(True),'Secondary.TButton'),
            ('Avvia Supporto',self.start,'Primary.TButton'),
            ('Ferma · F8',self.stop,'Stop.TButton')):
            ttk.Button(bar,text=label,command=command,style=style).pack(anchor='w',pady=3)
        ttk.Checkbutton(panel,text='Modalità test (ON: simula · OFF: invia tasti reali)',
                        variable=self.dry,command=self.mode_changed).pack(anchor='w',pady=5)
        self.window_text=tk.StringVar(value='Finestra da scegliere ad ogni avvio; ROI salvata separatamente.')
        testo(panel,textvariable=self.window_text,role='technical')
        columns=Colonne(parent)
        monitor=pannello(columns.sinistra,'Monitor HP','HP presenti e cura accodata: stime visive sperimentali.')
        self.hp=tk.StringVar(value='HP utilizzati: —')
        testo(monitor,textvariable=self.hp,role='section_title')
        self.hp_detail=tk.StringVar(value='Grezzi: —   ·   Filtrati: —   ·   Confidence: —')
        testo(monitor,textvariable=self.hp_detail,role='technical')
        self.recovery_text=tk.StringVar(value='In recupero: — · HP previsti: —')
        testo(monitor,textvariable=self.recovery_text,role='secondary')
        self.heal_state=tk.StringVar(value='Auto Cura: READY')
        testo(monitor,textvariable=self.heal_state,role='status')
        self.error=tk.StringVar(value=('Calibrazione caricata. Seleziona Metin2 e avvia il test.' if self.saved['roi'] and self.saved['color'] else 'Calibra con HP pieni e senza effetto di una pozione.'))
        testo(monitor,textvariable=self.error,role='technical')
        self.roi_text=tk.StringVar();self.update_roi()
        testo(monitor,textvariable=self.roi_text,role='technical')
        ttk.Checkbutton(monitor,text='Debug HP: ROI e maschera colore',variable=self.debug,
                        command=self.toggle_debug).pack(anchor='w',pady=4)
        self.debug_frame=ttk.Frame(monitor,style='Card.TFrame');self.debug_frame.pack(fill='x')
        self.preview=ttk.Label(self.debug_frame,text='La ROI analizzata apparirà qui.',anchor='center')
        self.preview.pack(fill='x',pady=6)
        self.mask_view=ttk.Label(self.debug_frame,text='Bianco = HP presenti · Grigio = cura accodata',anchor='center')
        self.mask_view.pack(fill='x',pady=3)
        heal=pannello(columns.destra,'Auto Cura','Un burst è una sola attivazione; riarmo e cooldown sono entrambi necessari.')
        self.auto=tk.BooleanVar(value=self.saved['auto_heal'])
        ttk.Checkbutton(heal,text='Auto Cura',variable=self.auto).pack(anchor='w',pady=4)
        self.field(heal,'Cura sotto (%)','threshold',1,98,1)
        self.field(heal,'Riarmo sopra (%)','rearm',2,100,1)
        self.keyfield(heal,'Tasto cura','heal_key')
        self.field(heal,'Usi per attivazione','uses',1,4,1)
        self.field(heal,'Intervallo tra usi (s)','burst_interval',.1,5,.1)
        self.field(heal,'Cooldown minimo (s)','cooldown',.2,120,.1)
        self.field(heal,'Letture HP al secondo','sample_hz',10,20,1)
        testo(heal,'F6 e F8 sono riservati. Le modifiche si applicano dopo Ferma e Avvia Supporto.',role='technical')
        mana=pannello(parent,'Mana opzionale','Disattivato: nessuna cattura della barra blu. HP e abilità restano indipendenti.')
        self.mana_values={}
        self.mana_enabled=tk.BooleanVar(value=self.saved['mana']['enabled'])
        ttk.Checkbutton(mana,text='Auto Mana',variable=self.mana_enabled).pack(anchor='w',pady=4)
        ttk.Button(mana,text='Calibra mana (5 s)',style='Secondary.TButton',
                   command=lambda:self.choose(True,'mp')).pack(anchor='w')
        self.mana_text=tk.StringVar(value='Mana: — · Auto Mana: OFF')
        self.mana_detail=tk.StringVar(value='Calibra con la barra blu piena, senza pozione attiva.')
        testo(mana,textvariable=self.mana_text,role='status')
        testo(mana,textvariable=self.mana_detail,role='technical')
        self.mana_roi=tk.StringVar(value=str(self.saved['mana']['roi'] or 'ROI mana non calibrata'))
        testo(mana,textvariable=self.mana_roi,role='technical')
        for label,key,lo,hi,step in (
            ('Usa pozione sotto (%)','threshold',1,98,1),('Riarmo sopra (%)','rearm',2,100,1),
            ('Usi per attivazione','uses',1,4,1),('Intervallo tra usi (s)','burst_interval',.1,5,.1),
            ('Cooldown minimo (s)','cooldown',.2,120,.1)):
            self.field(mana,label,key,lo,hi,step,resource='mana')
        self.keyfield(mana,'Tasto pozione blu','heal_key',resource='mana')
        self.mana_preview=ttk.Label(mana,text='Debug mana: ROI e maschera durante il test.',anchor='w')
        self.mana_preview.pack(fill='x',pady=4)
        self.mana_mask=ttk.Label(mana,text='Bianco = mana presente · Grigio = recupero stimato',anchor='w')
        self.mana_mask.pack(fill='x')
        self.mana_image_stamp=0
        abilities=pannello(parent,'Abilità temporizzate','Primo utilizzo immediato all’avvio, una abilità alla volta, con Metin2 in primo piano. Poi ogni timer segue il proprio intervallo; perde il focus, va in pausa.')
        testo(abilities,'Tasti personalizzati: scrivi anche ALT+1, CTRL+2 o SHIFT+F1. F6/F8 riservati.',role='technical')
        self.field(abilities,'Pausa tra abilità (s)','skill_gap',.1,10,.1)
        for i,skill in enumerate(self.saved['skills']):
            box=ttk.Frame(abilities,style='Card.TFrame',padding=(0,6));box.pack(fill='x')
            ttk.Label(box,text=f'Slot {i+1}',font=FONT['subsection_title']).grid(row=0,column=0,sticky='w')
            name=tk.StringVar(value=skill['name']);key=tk.StringVar(value=skill['key'])
            interval=tk.StringVar(value=f"{skill['interval']:g}");enabled=tk.BooleanVar(value=skill['enabled'])
            countdown=tk.StringVar(value='OFF' if not skill['enabled'] else 'Da avviare')
            ttk.Entry(box,textvariable=name,width=22).grid(row=0,column=1,sticky='ew',padx=8)
            ttk.Checkbutton(box,text='Attiva',variable=enabled).grid(row=0,column=2,sticky='w')
            ttk.Label(box,text='Tasto').grid(row=1,column=0,sticky='w')
            ttk.Combobox(box,textvariable=key,values=KEYS,state='normal',width=10).grid(row=1,column=1,sticky='w',padx=8,pady=3)
            ttk.Label(box,textvariable=countdown,foreground=COLORI['muted']).grid(row=1,column=2,sticky='w')
            ttk.Label(box,text='Intervallo (s)').grid(row=2,column=0,sticky='w')
            ttk.Spinbox(box,textvariable=interval,from_=1,to=86400,increment=1,width=10).grid(row=2,column=1,sticky='w',padx=8)
            box.columnconfigure(1,weight=1)
            self.skills.append((name,key,interval,enabled,countdown))
        save=pannello(parent,'Configurazione Supporto')
        ttk.Button(save,text='Salva Supporto',style='Primary.TButton',command=self.save).pack(anchor='w')
        log=pannello(parent,'Eventi Supporto','Solo cambi di stato, errori e input. Nessuna riga per ogni frame.')
        self.log=tk.Text(log,height=8,width=40,wrap='word',state='disabled',font=FONT['technical'],
                         background=COLORI['input'],foreground=COLORI['muted'],relief='flat')
        self.log.pack(fill='x')
        self.poll_job=root.after(100,self.poll)

    def mode_changed(self):
        self.stop()
        self.status.set('FERMO — '+('Modalità test: nessun tasto reale.' if self.dry.get() else 'INPUT REALI selezionati. Premi Avvia Supporto per partire.'))

    def field(self,parent,label,key,lo,hi,step,resource=None):
        text=ttk.Frame(parent,style='Card.TFrame');text.pack(fill='x',pady=3)
        ttk.Label(text,text=label).pack(anchor='w')
        v=tk.StringVar(value=str((self.saved[resource] if resource else self.saved)[key]));(self.mana_values if resource else self.values)[key]=v
        ttk.Spinbox(text,textvariable=v,from_=lo,to=hi,increment=step,width=10).pack(anchor='w',pady=2)

    def keyfield(self,parent,label,key,resource=None):
        testo(parent,label,role='label')
        v=tk.StringVar(value=(self.saved[resource] if resource else self.saved)[key]);(self.mana_values if resource else self.values)[key]=v
        ttk.Combobox(parent,textvariable=v,values=KEYS,state='normal',width=10).pack(anchor='w')
        testo(parent,'Tasto o combinazione: Q, ALT+1, CTRL+2, SHIFT+F1, CTRL+ALT+Q.',role='technical')

    def collect(self):
        data=dict(self.saved)
        data.update({key:value.get() for key,value in self.values.items()})
        data['mana']=dict(self.saved['mana'],enabled=self.mana_enabled.get(),**{k:v.get() for k,v in self.mana_values.items()})
        data['auto_heal']=self.auto.get()
        data['dry_run']=self.dry.get()
        data['skills']=[dict(name=n.get(),key=k.get(),interval=i.get(),enabled=e.get())
                        for n,k,i,e,_ in self.skills]
        return validate(data)

    def save(self):
        try:
            config=self.collect()
            aggiorna_configurazione(self.path,{'supporto':config})
            self.saved=config
            self.values['heal_key'].set(config['heal_key'])
            self.mana_values['heal_key'].set(config['mana']['heal_key'])
            for variables,skill in zip(self.skills,config['skills']):
                variables[1].set(skill['key'])
            self.status.set('Supporto salvato. Ferma e riavvia il test per applicare le modifiche.')
            return config
        except (ValueError,OSError) as e:
            self.status.set(str(e));return None

    def update_roi(self):
        self.roi_text.set(f"ROI relativa: {self.saved['roi'] or 'non calibrata'} · dimensioni: {self.saved['window_size'] or '—'}")

    def toggle_debug(self):
        if self.debug.get():self.debug_frame.pack(fill='x');self.image_stamp=None
        else:self.debug_frame.pack_forget()

    def choose(self, calibration=False, resource="hp"):
        self.stop();code=self.selection
        def countdown(n):
            if self.closed or code!=self.selection:return
            if n:
                self.status.set(f'Porta Metin2 in primo piano entro {n} s'+(f' — {"Mana pieno" if resource=="mp" else "HP pieni"}, nessuna pozione attiva.' if calibration else '.'))
                self.root.after(1000,lambda:countdown(n-1));return
            try:
                from cattura_metin import api_windows,area_interna
                u=api_windows();hwnd=u.GetForegroundWindow()
                title=ctypes.create_unicode_buffer(u.GetWindowTextLengthW(hwnd)+1)
                u.GetWindowTextW(hwnd,title,len(title))
                if 'metin2' not in title.value.casefold():raise ValueError('La finestra selezionata non è Metin2.')
                area=area_interna(u,hwnd);self.hwnd=hwnd
                self.window_text.set('Metin2: '+title.value)
                if not calibration:
                    self.status.set('Metin2 selezionato. '+('Calibrazione disponibile: avvia test.' if self.saved['roi'] and self.saved['color'] else 'Calibra HP oppure avvia i timer in test.'));return
                import mss
                from PIL import Image
                with mss.mss() as capture:
                    shot=capture.grab(area)
                if u.GetForegroundWindow()!=hwnd or area_interna(u,hwnd)!=area:
                    raise ValueError('Finestra spostata durante la cattura: riprova.')
                image=Image.frombytes('RGB',shot.size,shot.rgb)
                def selected(roi):
                    self.dialog=None
                    if code!=self.selection or self.closed:return
                    if roi is None:self.status.set('Calibrazione annullata.');return
                    try:
                        x,y,w,h=roi
                        profile=calibrate(image.crop((x,y,x+w,y+h)),kind=resource)
                        data=dict(self.saved)
                        calibration_data=dict(roi=list(roi),window_size=list(image.size),color=profile)
                        if resource=='mp':data['mana']=dict(data['mana'],**calibration_data)
                        else:data.update(calibration_data)
                        data=validate(data)
                        aggiorna_configurazione(self.path,{'supporto':data})
                        self.saved=data;self.update_roi()
                        self.mana_roi.set(str(data['mana']['roi'] or 'ROI mana non calibrata'))
                        (self.mana_detail if resource=='mp' else self.error).set('Calibrazione salvata: '+str(len(profile['rows']))+' linee; bordi esclusi. Avvia test.')
                        self.logger.info('Supporto: calibrazione %s salvata, ROI=%s',resource,list(roi))
                        self.status.set('Calibrazione salvata. Controlla Modalità test e premi Avvia Supporto.')
                    except (ValueError,OSError) as e:
                        message=str(e) if resource=='hp' else str(e).replace('HP','mana').replace('rosso','blu')
                        self.status.set('Calibrazione non salvata: '+message)
                        (self.mana_detail if resource=='mp' else self.error).set('Calibrazione non salvata: '+message)
                self.status.set('Seleziona SOLO l’interno '+('blu della barra mana piena' if resource=='mp' else 'rosso della barra HP piena')+', senza bordi, testo o icone.')
                self.dialog=self.select_area(self.root,image,selected)
            except Exception as e:
                self.status.set('Selezione non riuscita: '+str(e))
        countdown(5)

    def start(self):
        if self.thread and self.thread.is_alive():
            self.status.set('Sessione presente: premi Ferma e attendi un istante prima di riavviare.');return
        if not self.hwnd:self.status.set('Prima scegli la finestra Metin2.');return
        config=self.save()
        if config is None:return
        if config['roi'] and config['color'] and ('span' not in config['color'] or 'bright_rows' not in config['color']):
            self.status.set('Ricalibra HP una volta: serve il profilo luminosità della barra piena.')
            self.error.set('Profilo precedente: premi Calibra HP con barra piena e senza cura attiva.')
            return
        if config['auto_heal'] and (not config['roi'] or not config['color']):
            self.status.set('Calibra la barra HP prima di simulare Auto Cura.');return
        if config['mana']['enabled'] and (not config['mana']['roi'] or not config['mana']['color'] or 'bright_rows' not in config['mana']['color']):
            self.status.set('Calibra la barra mana piena prima di attivare Auto Mana.');return
        self.selection+=1
        self.snapshots=queue.Queue(maxsize=1);self.events=queue.Queue(maxsize=200)
        self.stop_event=threading.Event();self.image_stamp=None
        self.thread=threading.Thread(target=run_support,args=(self.hwnd,config,self.stop_event,self.snapshots,self.events),daemon=True)
        self.thread.start();self.status.set('Avvio — '+('DRY RUN' if config['dry_run'] else 'INPUT REALI'))

    def stop(self):
        self.selection+=1
        if self.stop_event:self.stop_event.set()
        if self.dialog is not None:
            self.dialog.destroy();self.dialog=None
        self.status.set('FERMO — nessun input Supporto')
        self.hp.set('HP utilizzati: —')
        self.mana_text.set('Mana: — · FERMO')
        self.recovery_text.set('In recupero: — · HP previsti: —')
        for *_,countdown in self.skills:countdown.set('Fermo')

    def close(self):
        if self.closed:return
        self.stop();self.closed=True
        self.root.after_cancel(self.poll_job)
        if self.thread:self.thread.join(timeout=.3)

    def poll(self):
        if self.closed:return
        try:
            while True:
                timestamp,message=self.events.get_nowait()
                self.logger.info('Supporto: %s',message)
                self.log.configure(state='normal')
                self.log.insert('end',datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')+' — '+message+'\n')
                if int(self.log.index('end-1c').split('.')[0])>200:self.log.delete('1.0','2.0')
                self.log.see('end');self.log.configure(state='disabled')
        except queue.Empty:pass
        try:sample=self.snapshots.get_nowait()
        except queue.Empty:sample=None
        if sample and self.stop_event and not self.stop_event.is_set():
            self.status.set(sample['status']);self.heal_state.set('Auto Cura: '+sample['state'])
            def percent(value):return '—' if value is None else f'{value:.1f}%'
            mp=sample.get('mana',{})
            self.mana_text.set('Mana utilizzato: '+percent(mp.get('used'))+' · '+sample.get('mana_state','OFF'))
            self.mana_detail.set(f"Grezzi: {percent(mp.get('raw'))} · Filtrati: {percent(mp.get('used'))} · Previsti: {percent(mp.get('predicted'))} · Recupero: {percent(mp.get('recovery'))} · Confidence: {mp.get('confidence',0):.2f}\n"+(mp.get('error') or ''))
            if self.debug.get() and mp.get('image') and datetime.now().timestamp()-self.mana_image_stamp>.2:
                from PIL import Image,ImageTk
                size,data=mp['image'];im=Image.frombytes('RGB',size,data)
                factor=min(3,max(1,self.mana_preview.winfo_width()-12)/im.width,100/im.height)
                target=(max(1,round(im.width*factor)),max(1,round(im.height*factor)))
                self.mp_photo=ImageTk.PhotoImage(im.resize(target));self.mana_preview.configure(image=self.mp_photo,text='')
                if mp.get('mask'):
                    size,data=mp['mask'];im=Image.frombytes('L',size,data)
                    self.mp_mask_photo=ImageTk.PhotoImage(im.resize(target));self.mana_mask.configure(image=self.mp_mask_photo,text='')
                self.mana_image_stamp=datetime.now().timestamp()
            self.hp.set('HP utilizzati: '+percent(sample.get('used')))
            self.hp_detail.set(f"Grezzi: {percent(sample.get('raw'))} · Filtrati: {percent(sample.get('filtered'))} · Confidence: {sample.get('confidence',0):.2f} · {sample.get('fps',0):.1f} letture/s")
            self.recovery_text.set(f"In recupero: {percent(sample.get('recovery'))} · HP previsti: {percent(sample.get('predicted'))}")
            self.error.set(sample.get('error') or 'Stime sperimentali · riarmo sugli HP presenti filtrati.')
            for values,remaining in zip(self.skills,sample.get('countdowns',[])):
                values[-1].set('OFF' if remaining is None else f'Prossimo: {remaining:.1f} s')
            if self.debug.get() and sample.get('image') and sample.get('image_time')!=self.image_stamp:
                from PIL import Image,ImageTk
                size,data=sample['image'];image=Image.frombytes('RGB',size,data)
                factor=min(3,max(1,self.preview.winfo_width()-12)/image.width,120/image.height)
                target=(max(1,round(image.width*factor)),max(1,round(image.height*factor)))
                self.photo=ImageTk.PhotoImage(image.resize(target));self.preview.configure(image=self.photo,text='')
                if sample.get('mask'):
                    size,data=sample['mask'];image=Image.frombytes('L',size,data)
                    self.mask_photo=ImageTk.PhotoImage(image.resize(target));self.mask_view.configure(image=self.mask_photo,text='')
                self.image_stamp=sample['image_time']
            if sample.get('traceback'):self.logger.error(sample['traceback'])
            if sample.get('ended'):self.stop_event.set()
        self.poll_job=self.root.after(100,self.poll)
