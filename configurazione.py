"""Shared atomic configuration updates; writes are made by the Tk main thread."""
import json
from pathlib import Path


def leggi_configurazione(path):
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Formato impostazioni non valido.')
    return data


def aggiorna_configurazione(path, values):
    path = Path(path)
    data = leggi_configurazione(path)
    data.update(values)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
