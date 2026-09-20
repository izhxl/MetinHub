"""Manutenzione MetinHub. Solo libreria standard; nessuna lettura del gioco."""
import argparse
import ctypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parent
MAX_DOWNLOAD = 25 * 1024 * 1024
RESERVED = {'metinhub_settings.json','metinhub_log.txt','install-state.json','installazione_log.txt'}

def versione(v):
    if not isinstance(v,str) or not re.fullmatch(r'\d+\.\d+\.\d+',v):
        raise ValueError('Versione non valida: usare x.y.z.')
    return tuple(map(int,v.split('.')))

def https_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ValueError('Serve un indirizzo HTTPS senza credenziali nella URL.')
    return url

def leggi_manifest(url):
    https_url(url)
    with urllib.request.urlopen(url,timeout=20) as r:
        https_url(r.geturl())
        raw=r.read(65537)
    if len(raw)>65536: raise ValueError('Manifest troppo grande.')
    obj=json.loads(raw)
    if obj.get('product')!='MetinHub' or obj.get('format')!=1:
        raise ValueError('Il file non e un manifest MetinHub supportato.')
    versione(obj.get('version'))
    https_url(obj.get('url',''))
    if not re.fullmatch('[a-fA-F0-9]{64}',obj.get('sha256','')):
        raise ValueError('SHA-256 mancante o non valido.')
    return obj

def scarica_pacchetto(manifest, folder):
    dest=Path(folder)/'aggiornamento.zip'
    total=0; digest=hashlib.sha256()
    try:
        with urllib.request.urlopen(https_url(manifest['url']),timeout=30) as r, dest.open('wb') as out:
            https_url(r.geturl())
            while True:
                block=r.read(65536)
                if not block: break
                total+=len(block)
                if total>MAX_DOWNLOAD: raise ValueError('Pacchetto troppo grande.')
                digest.update(block);out.write(block)
        if digest.hexdigest().lower()!=manifest['sha256'].lower():
            raise ValueError('SHA-256 diverso da quello pubblicato: download rifiutato.')
        return dest
    except Exception:
        dest.unlink(missing_ok=True)
        raise

def estrai_pacchetto(archive, folder):
    allowed={'.py','.ps1','.bat','.txt','.cs','.manifest','.ico','.png','.svg','.json','.md'}
    names=set();entries=[]
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist())>100 or sum(i.file_size for i in z.infolist())>50*1024*1024:
            raise ValueError('Dimensioni archivio non consentite.')
        for entry in z.infolist():
            if entry.is_dir():continue
            p=PurePosixPath(entry.filename)
            if len(p.parts)!=2 or p.parts[0]!='MetinHub' or p.name.lower() in RESERVED or ':' in p.name or '\\' in p.name:
                raise ValueError('Percorso non consentito: '+entry.filename)
            if p.suffix.lower() not in allowed or p.name.startswith('.') or p.name.lower() in names:
                raise ValueError('File non consentito o duplicato: '+p.name)
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Link simbolico non consentito.')
            names.add(p.name.lower());entries.append((entry,p.name))
        if not {'osserva_metin.py','Installa_MetinHub.ps1'.lower(),'manutenzione_metin.py','version.txt'} <= names:
            raise ValueError('Pacchetto incompleto.')
        Path(folder).mkdir(parents=True,exist_ok=True)
        for entry,name in entries:
            with z.open(entry) as inp,(Path(folder)/name).open('wb') as out:
                shutil.copyfileobj(inp,out)
    return [name for _,name in entries]

def attendi_chiusura(pid):
    if not pid:return
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];k.WaitForSingleObject.restype=ctypes.c_uint32
    k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x00100000,False,pid)
    if h:
        try:
            if k.WaitForSingleObject(h,60000)!=0:raise RuntimeError('MetinHub non si e chiuso: manutenzione annullata.')
        finally:k.CloseHandle(h)
    time.sleep(0.4)

def log(text):
    print(text,flush=True)
    with (BASE/'manutenzione_log.txt').open('a',encoding='utf-8') as f:
        f.write(datetime.now().isoformat(timespec='seconds')+' | '+text+'\n')

def run(command):
    log('Esecuzione: '+' '.join(map(str,command)))
    env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with subprocess.Popen(command,cwd=BASE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',env=env) as p:
        for line in p.stdout:log(line.rstrip())
        if p.wait()!=0:raise RuntimeError('Comando fallito. Vedi manutenzione_log.txt.')

def setup():
    ps=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(ps),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(BASE/'Installa_MetinHub.ps1'),'-Worker'],cwd=BASE,capture_output=True,text=True,errors='replace')
    log(result.stdout+result.stderr)
    if result.returncode or 'SUCCESS' not in result.stdout.splitlines():
        raise RuntimeError('Installazione non completata: vedi installazione_log.txt.')

def componenti_gpu(cpu=False):
    if not cpu:
        smi=shutil.which('nvidia-smi')
        if not smi: raise RuntimeError('Driver NVIDIA con nvidia-smi non rilevato. Installa un driver compatibile dal sito NVIDIA e riprova.')
        run([smi,'--query-gpu=name,driver_version','--format=csv,noheader'])
    index='cpu' if cpu else 'cu128'
    command=[sys.executable,'-m','pip','install','--force-reinstall','torch==2.9.1','torchvision==0.24.1','--index-url','https://download.pytorch.org/whl/'+index,'--timeout','30','--retries','2']
    try:
        run(command)
        run([sys.executable,str(BASE/'setup_check.py'),'imports' if cpu else 'gpu'])
    except Exception:
        if cpu:raise
        log('GPU non pronta: tento il ripristino CPU.')
        componenti_gpu(cpu=True)
        raise RuntimeError('La GPU non e stata attivata. Librerie CPU ripristinate; vedi il registro.')

def aggiorna(archive):
    with tempfile.TemporaryDirectory(prefix='MetinHub-update-') as t:
        names=estrai_pacchetto(archive,t)
        backup=BASE/'backup_aggiornamenti'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        backup.mkdir(parents=True)
        modified=[]
        try:
            for name in names:
                dest=BASE/name
                if dest.exists():shutil.copy2(dest,backup/name)
                modified.append(name)
                shutil.copy2(Path(t)/name,dest)
            setup()
        except Exception:
            for name in reversed(modified):
                dest=BASE/name;old=backup/name
                if old.exists():shutil.copy2(old,dest)
                else:dest.unlink(missing_ok=True)
            raise RuntimeError('Aggiornamento non completato: file applicazione ripristinati. Le librerie potrebbero richiedere una verifica tramite installer.')
        log('Aggiornamento applicato. Backup: '+str(backup))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['gpu','cpu','setup','update'])
    parser.add_argument('--pid',type=int,default=0)
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    try:
        attendi_chiusura(args.pid)
        if args.action=='gpu':componenti_gpu()
        elif args.action=='cpu':componenti_gpu(cpu=True)
        elif args.action=='setup':setup()
        else:
            if not args.archive:raise ValueError('Pacchetto mancante.')
            aggiorna(args.archive)
        log('Operazione completata. Puoi riaprire MetinHub dal collegamento.')
    except Exception as e:log('ERRORE: '+str(e))
    input('\nPremi Invio per chiudere questa finestra...')

if __name__=='__main__':main()
