# Verifiche di MetinHub 0.0.1

## Eseguite nell'ambiente di sviluppo

- Sintassi di tutti i sorgenti Python.
- Nove test con `python -m unittest discover -s tests -v`.
- Release generata e accettata dal vero estrattore usato dall'updater.
- Rifiuto di percorsi estranei e file personali nei pacchetti.
- Hash del manifest coerente con lo ZIP appena creato.
- Regressione del conflitto Tkinter `_root` e risoluzione nativa dei widget,
  con inizializzazione grafica simulata e interprete Tcl reale, senza display.
- Scheduler del banner non rimandato indefinitamente dagli eventi di resize.
- Limite di larghezza dei comandi e ritorno alla disposizione verticale.
- Coerenza dei nomi delle risorse e dei file richiesti da installazione/disinstallazione.
- Confronto dei motori OCR/Pesca e delle funzioni operative col prototipo:
  comportamento conservato, con rinomina di prodotto/registro dove necessaria.

Questi test non costituiscono una prova completa della GUI Windows.

## Da provare su Windows

1. Installazione in una cartella nuova, avviatore EXE, icona, collegamenti e
   voce MetinHub nelle App installate.
2. Apertura delle quattro pagine; F6/F8 e chiusura regolare.
3. Finestra normale, massimizzata e resize continuo a 150% su schermo 4K.
4. Menu a tendina, input numerici, toggle, focus tastiera e scrollbar.
5. Scelta finestra/area e anteprima reale Schegge.
6. Pesca in simulazione e poi verifica della funzione già esistente nel gioco.
7. Salvataggio e ricaricamento delle preferenze.
8. Aggiornamento con una successiva release e un canale HTTPS reale.

In questo ambiente non sono disponibili Windows, il compilatore .NET Windows
né un display Tk. Non è stato prodotto né eseguito un EXE Windows qui.
La velocità effettiva del ridimensionamento e le integrazioni con il gioco
restano da confermare sul PC di destinazione.
