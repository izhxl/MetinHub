# Changelog

## 0.1.1

- Modalità A bersaglio per gli slot abilità, con calibrazione persistente.
- Lettura della piccola ROI: pronta, oscuramento compatibile con cooldown e stato incerto.
- Tentativi ripetuti; timer avviato solo dopo conferma visiva persistente.
- Verifica dell'icona pronta anche alla scadenza dell'intervallo.
- Abilità A tempo invariate: nessuna cattura dell'icona necessaria.
- Stati, confidenza e motivi di lettura visibili nella pagina Supporto.
- Corretto il filtro mana quando la ROI HP non è calibrata.
- Nessun riconoscimento delle icone pozione incluso: è il prossimo sviluppo.

## 0.1.0

- Sezione Supporto con calibrazione persistente e lettura HP filtrata.
- Auto Cura reale o simulata, burst, cooldown e soglia separata di riarmo.
- Mana opzionale con ROI e configurazione indipendenti.
- Stima visiva del recupero HP/MP già accodato.
- Cinque abilità con primo utilizzo immediato, sequenza e timer indipendenti.
- Tasti personalizzabili e combinazioni CTRL/ALT/SHIFT.
- Pausa su perdita focus, rilascio input e arresto con F8.
- Diagnostica e salvataggio impostazioni condivisi.
- Canale aggiornamenti GitHub predefinito; canali personalizzati conservati.
- Schegge, Pesca e interfaccia esistenti mantenuti.

## 0.0.1

Prima base MetinHub, derivata dal prototipo MetinOCR 0.14.1 corretto.

- Nome MetinHub in applicazione, installer, launcher, collegamenti e disinstallazione.
- Configurazione e registro dedicati `metinhub_settings.json` e `metinhub_log.txt`.
- Schegge, Pesca, Impostazioni e Installazione conservate.
- Anteprime adattive, controlli condivisi e correzione del conflitto Tkinter `_root`.
- Banner aggiornato periodicamente durante il resize, senza aspettare che il trascinamento finisca.
- Pannello comandi Schegge con larghezza contenuta sulle finestre grandi.
- Base repository, test e generatore di release con elenco esplicito dei file.

La nuova numerazione è indipendente da quella del prototipo. Nessuna migrazione
in-place o aggiornamento automatico da MetinOCR è previsto in questa versione.
