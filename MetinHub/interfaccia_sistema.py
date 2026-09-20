"""Scheda sistema: controlli asincroni e manutenzione confermata dall'utente."""
from pathlib import Path
import os
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import manutenzione_metin as maintenance


def aggiungi_sistema(parent, root, version, url_var, shutdown):
    base=Path(__file__).resolve().parent
    python=Path(sys.executable).with_name('python.exe')
    from tema_metin import pannello, testo, Colonne, FONT, COLORI, stato_evidenza, RiepilogoComponenti
    componenti=pannello(parent, 'Stato del computer', 'MetinHub '+version+' · Controlla i componenti prima di installare o riparare.')
    info=tk.StringVar(value='Controllo componenti disponibile. Le installazioni richiedono la tua conferma.')
    stato_evidenza(componenti,info)
    componenti.configure(padding=(10,6))
    component_rows=RiepilogoComponenti(componenti)
    report=tk.Text(componenti,width=30,height=7,wrap='word',state='disabled',
                   background=COLORI['input'],foreground=COLORI['muted'],font=FONT['technical'],spacing1=2,spacing3=2,
                   relief='flat',borderwidth=0,highlightthickness=1,highlightbackground=COLORI['border'],padx=12,pady=12)
    def dettagli_tecnici():
        if report.winfo_manager():
            report.pack_forget();details.configure(text='Mostra dettagli tecnici')
        else:
            report.pack(fill='both',expand=True,pady=(12,6));details.configure(text='Nascondi dettagli tecnici')
    details=ttk.Button(componenti,text='Mostra dettagli tecnici',style='Ghost.TButton',command=dettagli_tecnici)
    details.pack(anchor='w',pady=(4,0))
    q=queue.Queue();busy=[False];pending=[None]
    def mostra(text):
        component_rows.mostra(text)
        report.configure(state='normal');report.delete('1.0','end');report.insert('end',text);report.configure(state='disabled')
    def background(fn,kind):
        if busy[0]:return
        busy[0]=True;info.set('Operazione in corso...')
        def task():
            try:q.put((kind,fn(),None))
            except Exception as e:q.put((kind,None,str(e)))
        threading.Thread(target=task,daemon=True).start()
    def verifica():
        def check():
            env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
            p=subprocess.run([str(python),str(base/'setup_check.py'),'diagnostics'],capture_output=True,text=True,errors='replace',timeout=60,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            return p.stdout+p.stderr+('\nVerifica incompleta: usa Verifica e ripara componenti.' if p.returncode else '')
        background(check,'report')
    def avvia_manutenzione(action,archive=None):
        command=[str(python),str(base/'manutenzione_metin.py'),action,'--pid',str(os.getpid())]
        if archive:command.extend(['--archive',str(archive)])
        try:
            subprocess.Popen(command,cwd=base,creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError as e:messagebox.showerror('Manutenzione',str(e),parent=root);return
        shutdown()
    def installa(action):
        if busy[0]:return
        text={'gpu':'Installare le librerie GPU NVIDIA (CUDA 12.8)? Il download puo occupare diversi GB. Il programma si chiudera. Se la verifica fallisce, verra tentato il ripristino CPU. I driver non vengono installati da questa procedura.',
              'cpu':'Ripristinare le librerie CPU? Il programma si chiudera e scarichera i componenti necessari.',
              'setup':'Verificare e installare/riparare i componenti mancanti? Il programma si chiudera; la procedura puo scaricare Python, librerie e modelli e aggiornare i collegamenti Windows.'}[action]
        if messagebox.askyesno('Conferma installazione',text,parent=root):avvia_manutenzione(action)
    spazio=Colonne(parent)
    manutenzione=pannello(spazio.sinistra,'Componenti e riparazione','Verifica prima lo stato; installazioni e ripristini richiedono conferma.')
    row=ttk.Frame(manutenzione,style='Card.TFrame');row.pack(fill='x',pady=4)
    row.columnconfigure(0,weight=1)
    for index,(label,fn) in enumerate([('Verifica componenti',verifica),('Verifica e ripara componenti',lambda:installa('setup')),('Installa supporto GPU',lambda:installa('gpu')),('Ripristina CPU',lambda:installa('cpu'))]):
        ttk.Button(row,text=label,style='Primary.TButton' if index==0 else 'Secondary.TButton',command=fn).grid(row=index,column=0,sticky='w',pady=(3,8) if index==0 else (3,3))
    box=pannello(spazio.destra,'Aggiornamenti','Gestisci il canale di distribuzione del progetto.')
    versione_bar=ttk.Frame(box,style='Card.TFrame')
    versione_bar.pack(fill='x',pady=(2,8))
    ttk.Label(versione_bar,text='VERSIONE CORRENTE',font=FONT['caption'],foreground=COLORI['muted']).pack(side='left')
    ttk.Label(versione_bar,text=version,font=FONT['status'],padding=(10,3),
              background=COLORI['input']).pack(side='right')
    ttk.Separator(box,orient='horizontal').pack(fill='x',pady=(0,8))
    testo(box,'STATO CONTROLLO',role='caption')
    testo(box,textvariable=info,role='status')
    testo(box,'Canale aggiornamenti (indirizzo HTTPS)',role='label')
    ttk.Entry(box,textvariable=url_var,width=30).pack(fill='x',pady=4)
    testo(box,'Salva l’indirizzo dalle Impostazioni. Usa solo il canale del progetto.',role='technical')
    def cerca():
        url=url_var.get().strip()
        if not url:
            messagebox.showinfo('Aggiornamenti','Canale non configurato. Occorre prima pubblicare il pacchetto e il manifest su un indirizzo HTTPS stabile.',parent=root);return
        pending[0]=None
        background(lambda:maintenance.leggi_manifest(url),'manifest')
    def scarica():
        if not pending[0] or busy[0]:return
        obj=pending[0]
        text='Scaricare e installare MetinHub '+obj['version']+' da:\n'+obj['url']+'\n\nIl programma si chiudera solo dopo download e verifica SHA-256. I file precedenti saranno conservati in backup.'
        if not messagebox.askyesno('Conferma aggiornamento',text,parent=root):return
        def download():
            folder=Path(tempfile.mkdtemp(prefix='MetinHub-download-'))
            return maintenance.scarica_pacchetto(obj,folder)
        background(download,'download')
    br=ttk.Frame(box,style='Card.TFrame');br.pack(fill='x',pady=5)
    ttk.Button(br,text='Controlla aggiornamenti',style='Secondary.TButton',command=cerca).pack(fill='x',pady=4)
    update=ttk.Button(br,text='Scarica e installa',style='Primary.TButton',command=scarica,state='disabled');update.pack(fill='x',pady=4)
    testo(box,'Per disinstallare: Impostazioni Windows → App → MetinHub.',muted=True)
    def poll():
        try:
            while True:
                kind,data,error=q.get_nowait();busy[0]=False
                if error:info.set('Operazione non riuscita.');mostra(error);continue
                if kind=='report':mostra(data);info.set('Controllo terminato.')
                elif kind=='manifest':
                    if maintenance.versione(data['version'])>maintenance.versione(version):
                        pending[0]=data;update.configure(state='normal');info.set('Disponibile versione '+data['version'])
                        mostra(str(data.get('notes',''))[:10000])
                    else:update.configure(state='disabled');info.set('Nessuna versione piu recente sul canale configurato.')
                elif kind=='download':
                    avvia_manutenzione('update',data);return
        except queue.Empty:pass
        root.after(120,poll)
    root.after(120,poll)
    # Verifica soltanto: nessun download automatico all'avvio.
    root.after(500,verifica)
