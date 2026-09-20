"""Verifiche usate dall'installazione e dalla scheda Sistema; nessun input al gioco."""
import sys
import struct
import importlib


def main():
    # Conserva la codifica della console; sostituisce solo caratteri non rappresentabili.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(errors='backslashreplace')
    mode=sys.argv[1] if len(sys.argv)>1 else 'imports'
    if mode in ('tls','models'):
        # Applicazione: attivare il TLS nativo prima di importare EasyOCR/urllib.
        import truststore
        truststore.inject_into_ssl()
        print('HTTPS: verifica tramite archivio certificati del sistema (truststore).')
        if mode=='tls':return
    if mode=='python':
        import tkinter
        assert struct.calcsize('P')==8 and (3,12)<=sys.version_info[:2]<=(3,14)
        print(sys.executable)
        return
    if mode=='bootstrap':
        import tkinter
        from PIL import Image, ImageTk
        return
    errors=[]
    for name in ['torch','torchvision','easyocr','mss','pyautogui','cv2','tkinter','PIL.Image','PIL.ImageTk']:
        try:
            module=importlib.import_module(name)
            if mode=='diagnostics':print(name+': OK '+str(getattr(module,'__version__','')))
        except Exception as e:
            errors.append(name+': '+str(e))
            if mode=='diagnostics':print('MANCANTE/ERRORE '+errors[-1])
    if errors:raise RuntimeError('\n'.join(errors))
    import torch
    import torchvision
    print('Python',sys.version.split()[0],'| Torch',torch.__version__,'| Torchvision',torchvision.__version__)
    if mode=='diagnostics':
        print('CUDA inclusa nella libreria:',torch.version.cuda or 'no (versione CPU)')
        print('GPU CUDA disponibile:',torch.cuda.is_available())
        if torch.cuda.is_available():print('GPU:',torch.cuda.get_device_name(0))
        print('Se hai NVIDIA ma CUDA non e disponibile, usa Installa supporto GPU. I driver vanno installati separatamente.')
    if mode=='gpu':
        if not torch.cuda.is_available():raise RuntimeError('CUDA non disponibile dopo l installazione.')
        torch.set_num_threads(1)
        with torch.inference_mode():
            layer=torch.nn.Conv2d(3,8,3).cuda()
            result=layer(torch.zeros((1,3,32,32),device='cuda'))
            torch.cuda.synchronize()
            assert result.shape==(1,8,30,30)
        print('Calcolo GPU verificato:',torch.cuda.get_device_name(0))
    if mode=='models':
        import easyocr
        torch.set_num_threads(1)
        print('Verifica/download modelli OCR in corso. Attendere il messaggio Modelli OCR pronti.',flush=True)
        easyocr.Reader(['it','en'],gpu=False,verbose=False)
        print('Modelli OCR pronti.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('ERRORE:',e)
        if 'CERTIFICATE_VERIFY_FAILED' in str(e):
            print('HTTPS non verificabile anche con i certificati di sistema. Controllare data/ora di Windows, aggiornamenti e certificati della rete/proxy. Nessuna verifica TLS disattivata.')
        sys.exit(1)
