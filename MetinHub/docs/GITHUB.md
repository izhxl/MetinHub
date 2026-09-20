# Portare MetinHub su GitHub

## Primo caricamento

Crea il repository `MetinHub` sul tuo account. Per la prima prova puoi mantenerlo
privato. Carica il contenuto della cartella MetinHub estratta, mantenendo anche
`.gitignore` e `.gitattributes`. Non caricare il vecchio ambiente installato.

Se usi GitHub Desktop, aggiungi questa cartella come repository locale, controlla
le modifiche, crea il primo commit e usa Publish repository. In alternativa,
con Git installato e dalla cartella del progetto:

```text
git init
git add .
git status
git commit -m "MetinHub 0.0.1: prima base del progetto"
git branch -M main
git remote add origin URL_DEL_TUO_REPOSITORY
git push -u origin main
```

Sostituisci il segnaposto con il vero URL del repository. I comandi qui riportati
non sono stati eseguiti e non è stato creato un repository remoto.

## Prossime modifiche

1. Modifica i sorgenti nella stessa cartella.
2. Esegui `py -m unittest discover -s tests -v`.
3. Prova l'app su Windows: avvio, resize e funzione interessata dalla modifica.
4. Fai commit dei cambiamenti e push. Un commit non richiede sempre una release.
5. Quando vuoi distribuire una versione, aggiorna `VERSION.txt` e `CHANGELOG.md`.
6. Esegui `py tools\crea_release.py`: crea uno ZIP pulito in `dist`.
7. Crea un tag/release corrispondente, per esempio `v0.0.1`, e allega lo ZIP generato.

Il generatore e l'installer stampano la versione corrente anche nei metadati del
launcher; i sorgenti C# e manifest iniziali riportano 0.0.1.0.

## Aggiornamento dentro l'app

Il download automatico richiede due file pubblicamente raggiungibili tramite HTTPS:
lo ZIP generato e un manifest JSON. Un repository privato non basta: l'app non
contiene credenziali GitHub e non gestisce autenticazione per il download.

Dopo aver deciso l'URL dello ZIP, rigenera la release con:

```text
py tools\crea_release.py --url "URL_HTTPS_REALE_DELLO_ZIP"
```

Pubblica insieme lo ZIP appena generato e `latest.json` dalla stessa esecuzione;
il manifest contiene il suo hash esatto. Inserisci nell'app l'URL del manifest.
Non usare lo ZIP automatico dei sorgenti GitHub: cartella e contenuto non hanno
il formato richiesto dall'aggiornamento.

La release deve avere la cartella interna `MetinHub/` e file applicazione direttamente
al suo interno. L'updater rifiuta percorsi estranei, file personali e pacchetti
incompleti. Non togliere questi controlli per distribuire il repository intero.

MetinOCR usa un'identità di prodotto e una numerazione diverse: il primo passaggio
a MetinHub va fatto installando la nuova cartella separata.
