# MetinHub

**Versione 0.0.1 — prima base del progetto MetinHub.**

Applicazione desktop per Windows con strumenti Schegge e Pesca, impostazioni
condivise e manutenzione dei componenti. Deriva dal prototipo MetinOCR;
la numerazione riparte da 0.0.1 e non rappresenta un aggiornamento numericamente
successivo a MetinOCR 0.14.1.

## Avvio su Windows

1. Estrai tutta la cartella in una posizione permanente e scrivibile, ad esempio
   `C:\Users\TUO_NOME\Desktop\MetinHub`.
2. Esegui **Installa_MetinHub.bat** e avvia l'installazione dalla finestra.
3. Attendi la verifica di Python, librerie e modelli OCR. Al primo avvio serve Internet.
4. Apri **MetinHub** dal collegamento creato sul Desktop o nel menu Start.

L'installer genera localmente **MetinHub.exe**, l'avviatore con icona e richiesta
amministratore. Non è un eseguibile autonomo: usa i file Python e `.venv` presenti
nella stessa cartella. `Avvia_MetinHub.bat` è l'avvio alternativo.

La base attuale è destinata a Windows 10/11 x64 Intel/AMD. L'installer prova
Python 3.13, 3.12 e 3.14; conserva un ambiente già funzionante. Include la procedura
CPU e la manutenzione GPU già presenti nel prototipo. Non distribuire `.venv`.

## Pagine

- **Schegge:** scelta finestra, selezione area, OCR e inseguimento di un bersaglio
  alla volta. F6 avvia/mette in pausa; F8 arresta. L'intervallo configurato riguarda
  la ricerca senza bersaglio; l'inseguimento mantiene la modalità live.
- **Pesca:** scelta finestra, modalità continua, anteprima e indicatori;
  simulazione senza click e prova singola restano disponibili.
- **Impostazioni:** intervallo, rilascio del mouse, motore OCR e profilo CPU.
- **Installazione:** verifica/riparazione, supporto GPU, ripristino CPU e aggiornamenti.

Mantieni visibile la finestra del gioco e usa il monitor principale per l'input.
Seleziona nuovamente finestra e area nella nuova installazione. Non avviare
contemporaneamente MetinOCR e MetinHub mentre controllano il mouse.

## Passaggio da MetinOCR

Installa MetinHub in una **cartella separata**. Non spostare `.venv` e non
sovrascrivere la vecchia installazione: i collegamenti e la registrazione Windows
sono ora distinti. MetinHub salva `metinhub_settings.json` e `metinhub_log.txt`.

Per trasferire manualmente le preferenze, a programmi chiusi copia
`metinocr_settings.json` come `metinhub_settings.json` nella nuova cartella.
Il vecchio canale aggiornamenti non va riutilizzato: svuota `url_aggiornamenti`
nel JSON oppure configura il nuovo indirizzo prima di controllare aggiornamenti.
Le coordinate dell'area vanno scelte nuovamente dalla UI.

## Repository GitHub

Questa cartella è la radice del repository: carica **il suo contenuto**, non
un'altra cartella MetinHub annidata. Sono inclusi sorgenti, immagini, icona,
installer, documentazione, test e strumenti di distribuzione.

`.gitignore` esclude ambienti Python, log, impostazioni, catture e artefatti generati.
Prima del commit controlla comunque i file selezionati. I JSON `pesca_contatore.json`
e l'immagine `pesca_riferimento.png` sono risorse del programma e vanno mantenuti.

Non sono inclusi account, token, repository remoto o un canale aggiornamenti
inventato. Questo pacchetto non è stato pubblicato su GitHub.

## Sviluppo e release

La versione dell'app e dell'installer viene letta da **VERSION.txt**.

```bat
py -m unittest discover -s tests -v
py tools\crea_release.py
```

Il secondo comando crea `dist\MetinHub_0.0.1.zip` e il relativo SHA-256 usando
l'elenco esplicito `release-files.txt`. Lo ZIP ha la struttura richiesta dal
sistema di aggiornamento e non contiene file personali né directory di sviluppo.

Per produrre anche `latest.json`, dopo aver deciso l'URL HTTPS reale della release:

```bat
py tools\crea_release.py --url "URL_HTTPS_REALE_DELLO_ZIP"
```

Pubblica lo ZIP di **dist**, non lo ZIP del repository, come allegato della release.
Per i dettagli vedi [docs/GITHUB.md](docs/GITHUB.md).

## Stato delle verifiche

Vedi [docs/VERIFICHE.md](docs/VERIFICHE.md). Sintassi Python, pacchetti e test locali
sono verificati. La nuova installazione con nome MetinHub, la compilazione EXE e
la resa della GUI richiedono ancora una prova reale su Windows.

## Licenza

Non è stata assegnata una licenza di distribuzione al progetto. Prima di una
pubblicazione pubblica scegli una licenza e verifica i diritti delle risorse
incluse. Le dipendenze conservano le rispettive licenze.
