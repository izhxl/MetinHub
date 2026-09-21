# MetinHub

**Versione 0.1.0 — Windows 10/11 x64.**

App desktop con Schegge, Pesca, Supporto, Impostazioni e Installazione.

## Installazione

Scarica `MetinHub_0.1.0.zip` dagli allegati della release, estrai tutta la
cartella ed esegui `Installa_MetinHub.bat`. Avvia poi dal collegamento creato.
L'installer prepara Python, dipendenze e l'avviatore con icona `MetinHub.exe`.
Il launcher viene compilato sul PC Windows: non è un EXE autonomo e richiede
la cartella dell'app e il relativo ambiente. Primo avvio con Internet.
Avvio alternativo: `Avvia_MetinHub.bat`.

## Funzioni

- Schegge: OCR, selezione area relativa alla finestra, inseguimento live.
- Pesca: tracking del minigioco, modalità continua, prove e diagnostica.
- Supporto: HP, mana opzionale, cura con soglie/riarmo/cooldown e cinque timer abilità.
- Tasti Supporto personalizzabili: singoli o combinati, ad esempio `ALT+1`.
- Impostazioni persistenti e manutenzione CPU/GPU.

Supporto parte in modalità test a ogni apertura. Gli input reali si abilitano
esplicitamente; vengono sospesi quando Metin2 perde il focus. F8 ferma tutti
i moduli. F6 controlla il modulo previsto dalla pagina attiva.
Le letture HP/MP e del recupero sono stime visive. Vedi `SUPPORTO_LEGGIMI.txt`.

## Aggiornamenti

Canale stabile predefinito:
`https://github.com/izhxl/MetinHub/releases/latest/download/latest.json`

I canali personalizzati già salvati vengono mantenuti. Per usare quello
ufficiale, inserisci l'indirizzo sopra nella pagina Installazione e salvalo.
Il controllo/scaricamento segue il flusso esistente della pagina Installazione;
non è stata introdotta un'installazione silenziosa automatica.
Lo ZIP viene verificato tramite SHA-256. Versioni uguali non sono proposte
come aggiornamenti: le prove della 0.1.0 si applicano localmente.

## Repository e build

Carica il contenuto di questa cartella alla radice del repository.
Sono esclusi ambienti Python, log, impostazioni personali e catture di sessione.
Le risorse `pesca_contatore.json` e `pesca_riferimento.png` sono necessarie.

```bat
py -m unittest discover -s tests -v
py tools\crea_release.py --url https://github.com/izhxl/MetinHub/releases/download/v0.1.0/MetinHub_0.1.0.zip
```

Il secondo comando produce ZIP, SHA-256 e manifest in `dist`.
Pubblica questi file come allegati della release; non usare l'archivio dei
sorgenti GitHub per l'aggiornamento in-app. Non modificare lo ZIP dopo il calcolo
dell'hash. Procedura in `docs/GITHUB.md`; verifiche in `docs/VERIFICHE.md`.

Non è stata assegnata una nuova licenza in questa preparazione.
