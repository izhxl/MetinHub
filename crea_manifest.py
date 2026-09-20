"""Genera latest.json per una release ZIP gia' pronta."""
import argparse
import hashlib
import json
from pathlib import Path
from manutenzione_metin import https_url, versione
p=argparse.ArgumentParser()
p.add_argument('zip',type=Path)
p.add_argument('--version',required=True)
p.add_argument('--url',required=True)
p.add_argument('--notes',default='Aggiornamento MetinHub')
p.add_argument('--out',type=Path,default=Path('latest.json'))
a=p.parse_args()
versione(a.version);https_url(a.url)
data={'product':'MetinHub','format':1,'version':a.version,'url':a.url,'sha256':hashlib.sha256(a.zip.read_bytes()).hexdigest(),'notes':a.notes}
a.out.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
print('Creato:',a.out)
