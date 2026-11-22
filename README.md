# ha-plenitude

Integrazione personalizzata di Home Assistant per i consumi di luce dell'area clienti
[Eni Plenitude](https://eniplenitude.com/my-eni). Le credenziali si inseriscono una volta nella configurazione
guidata. I consumi orari vengono importati come statistiche storiche, con la loro data, e sono usabili nei
grafici e nella dashboard Energia. Funziona con ogni tipo di installazione di Home Assistant (OS, Container,
Core): è un'integrazione, non un add-on.

> **API non ufficiali.** Le chiamate sono state ricostruite il 2026-11-22 dal traffico della webapp e possono
> cambiare senza preavviso. Uso personale; poche richieste al giorno.

## Stato
- [x] Analisi delle API (login Gigya, sessione del portale, consumi quartorari, mensili per fascia)
- [x] Client asincrono indipendente da Home Assistant: `custom_components/plenitude/api.py`
- [x] Prototipo provato dal Mac (2026-11-22): login da script senza CAPTCHA, quarti d'ora di un giorno
- [x] Portale scaduto dopo meno di 55 minuti di inattività (`406`), rinnovato senza password (2026-11-22)
- [x] Integrazione: configurazione guidata, ri-autenticazione (password come riserva della sessione Gigya),
      import delle statistiche orarie, per fascia F1/F2/F3, per categoria stimata (giornaliere) e del costo
- [x] Test automatici (30) con il recorder vero di Home Assistant, su Home Assistant 2026.9.4 e 2026.10.4
- [x] Prova dal vivo (2026-11-22): primo import in 6 minuti, 7439 ore in 310 giorni (dal 4/1/2026 al 20/11),
      11 giorni mancanti; somme, fasce e costo coerenti; categorie su 321 giorni (anche nei giorni senza dati
      orari), con somma entro lo 0,2% del misurato; la sincronizzazione successiva chiede un solo giorno
- [ ] Tenuta della sessione Gigya di 30 giorni oltre le 24 ore (`prototipo.py stato` nei prossimi giorni)
- [x] Card distribuite con l'integrazione (2026-11-22): grafico dei consumi e bolletta in corso; logica delle date
      provata con Node, aspetto controllato su una pagina di prova con dati sintetici
- [ ] Prova delle card nel Home Assistant di casa
- [ ] Pubblicazione su GitHub e installazione da HACS

## Installazione
Con HACS: *HACS → menu → Repository personalizzati*, indirizzo del repository, tipo *Integrazione*; poi
installa *Eni Plenitude* e riavvia Home Assistant.

A mano: copia `custom_components/plenitude` nella cartella `custom_components` della configurazione di Home
Assistant (con Docker è la cartella montata su `/config`) e riavvia.

Poi *Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Eni Plenitude*, con email e password
dell'area clienti. Se l'account ha più forniture luce si sceglie quale importare.

Versione minima di Home Assistant: 2026.9 (i test girano su 2026.9.4 e 2026.10.4).

## Cosa fa
- **Sessione.** Al primo accesso chiede a Plenitude una sessione di 30 giorni; il portale scade dopo meno di
  un'ora di inattività e viene riaperto con la sessione, senza password. La password si usa solo quando la
  sessione di 30 giorni è finita. Se Plenitude rifiuta il login, Home Assistant chiede di inserirla di nuovo.
  Sessione e cookie stanno in `.storage/plenitude.<id>`, leggibile solo dal proprietario.
- **Primo import.** Scarica lo storico un giorno alla volta, all'indietro da ieri, finché trova 31 giorni di
  fila senza dati (al massimo 3 anni). Ci vogliono alcuni minuti; avviene in background.
- **Aggiornamenti.** Ogni 6 ore chiede i giorni nuovi (i dati arrivano con circa 2 giorni di ritardo). Una
  volta al giorno richiede anche i giorni mancanti delle ultime 2 settimane, nel caso arrivino in ritardo.
- **Cambio d'ora.** Gli orari si ricostruiscono dalla posizione dei valori, perché il server etichetta male i
  giorni del cambio; un giorno con un numero di valori diverso dalla sua durata non viene importato.

## Statistiche importate
`<p>` è `plenitude:luce_<chiave>`, dove la chiave è un hash del POD (il POD non viene salvato).

| Statistica | Unità | Contenuto |
|---|---|---|
| `<p>_consumo` | kWh | consumo misurato, ora per ora |
| `<p>_f1`, `<p>_f2`, `<p>_f3` | kWh | lo stesso consumo diviso per fascia ARERA (0 nelle ore delle altre fasce) |
| `<p>_costo` | EUR | kWh × prezzo della fascia, solo se il prezzo è configurato |
| `<p>_cat_<categoria>` | kWh | ripartizione **stimata** da Plenitude, un valore al giorno (a mezzanotte) |

Categorie: `refrigerare`, `standby`, `lavare`, `cucinare`, `comfort_ambientale`, `elettronica_luci`,
`ricarica_elettrica`, `altro`.

Sensori (per sapere a che punto è l'import): *Ultimo giorno disponibile*, *Consumo dell'ultimo giorno* e, con
il prezzo, *Costo dell'ultimo giorno*. Non hanno `state_class`: la storia è nelle statistiche.

**Dashboard Energia:** *Impostazioni → Dashboard → Energia → Aggiungi consumo dalla rete*, statistica
*Plenitude luce consumo*; come costo scegli *Usa un'entità che tiene traccia dei costi totali* e la
statistica *Plenitude luce costo*. Home Assistant non calcola il costo di una statistica importata con un
prezzo fisso: per questo il costo lo calcola l'integrazione.

## Card
L'integrazione porta con sé due card e le carica da sola in ogni dashboard: non vanno installate né aggiunte
alle risorse. Si trovano in *Modifica dashboard → Aggiungi card* (cercando "Plenitude") e si configurano
dall'editor visuale. Leggono le statistiche importate.

**Consumi** (`custom:plenitude-consumption-card`): grafico a colonne. Nelle impostazioni si scelgono il periodo
di default (giorno, settimana, mese, anno), la vista (totale, fasce, categorie) e l'unità (kWh o €). Sulla card
si cambiano periodo, vista e unità, ci si sposta avanti e indietro con le frecce e si torna agli ultimi dati.
Il passaggio del mouse (o il tocco) mostra i valori di ogni colonna; *Tabella* li mostra tutti. Le categorie sono
stime giornaliere, quindi non compaiono nella vista del giorno e solo in kWh.

```yaml
type: custom:plenitude-consumption-card
period: month      # day | week | month | year
view: bands        # total | bands | categories
unit: kwh          # kwh | eur
```

**Bolletta in corso** (`custom:plenitude-billing-card`): consumo e costo dall'inizio del periodo di
fatturazione all'ultimo giorno con dati, ripartiti per fascia, con l'avanzamento del periodo, una stima a fine
periodo (media dei giorni con dati × durata) e le colonne giorno per giorno. `start_date` è il primo giorno di un
qualsiasi periodo di fatturazione (lo si legge su una bolletta): i periodi si ripetono ogni `months` mesi da lì.
Le frecce mostrano i periodi passati, da confrontare con le bollette.

```yaml
type: custom:plenitude-billing-card
start_date: "2026-11-01"
months: 2          # 2 = bimestre, 1 = mese
```

Entrambe accettano `title` ed `entry` (l'id della voce, se ci sono più forniture). Colori: palette categoriale
validata per il daltonismo sugli sfondi chiaro e scuro delle card; le fasce sono sempre blu (F1), arancio (F2) e
verde acqua (F3).

## Prezzo
Plenitude non espone il prezzo dell'offerta, quindi va inserito nelle opzioni dell'integrazione
(*Configura*): nessuno, unico (monoraria), due fasce F1 e F23 (bioraria) o tre fasce F1, F2, F3. Se cambia,
il costo di tutto lo storico viene ricalcolato con il nuovo prezzo.

Fasce ARERA (delibera 181/06, tabella 1): F1 lunedì-venerdì 8-19; F2 lunedì-venerdì 7-8 e 19-23, sabato
7-23; F3 notti 23-7, domeniche e festivi. Festivi: 1 e 6 gennaio, lunedì di Pasqua, 25 aprile, 1 maggio,
2 giugno, 15 agosto, 1 novembre, 8, 25 e 26 dicembre. Il 4 ottobre (festa nazionale dal 2026) non è nella
tabella ARERA e per ora è trattato come giorno feriale.

## Limiti
- I consumi mensili per fascia del portale (`consumptionData`) non coincidono con i mesi di calendario dei
  dati orari (differenze del totale da -46% a +58% da un mese all'altro, 2026-11-22): sembrano periodi di
  lettura o di fatturazione. Per questo non vengono importati e non servono a verificare le fasce.
- Le statistiche di Home Assistant sono orarie: i quarti d'ora si sommano per ora.
- Le categorie sono stime di Plenitude e arrivano solo giorno per giorno.
- Solo luce; il gas non è ancora gestito.

## Struttura
```
custom_components/plenitude/
  api.py          client dell'area clienti (solo aiohttp, nessuna dipendenza da Home Assistant)
  bands.py        fasce ARERA e prezzi (nessuna dipendenza da Home Assistant)
  coordinator.py  sessione, scelta dei giorni da scaricare, import delle statistiche
  config_flow.py  configurazione guidata, ri-autenticazione, opzioni del prezzo
  sensor.py       sensori dell'ultimo giorno
  websocket.py    comando plenitude/info per le card (quali statistiche e prezzi, nessun valore)
  frontend/plenitude-cards.js   le due card (JavaScript senza dipendenze, SVG disegnato a mano)
scripts/prototipo.py   prova da riga di comando sul Mac
tests/                 test automatici; tests/live: prova dal vivo (manuale)
```

## Test
```sh
/opt/homebrew/bin/python3.14 -m venv ~/venvs/ha-plenitude-test
~/venvs/ha-plenitude-test/bin/pip install -r requirements-test.txt
~/venvs/ha-plenitude-test/bin/python -m pytest -q -p no:logging
```
Stessi test su un'altra versione di Home Assistant: un ambiente con il kit corrispondente (per la 2026.9.4,
`pytest-homeassistant-custom-component==0.13.367`).

Card: logica delle date (bimestri, cambio d'ora) con Node, aspetto su una pagina con dati sintetici:
```sh
TZ=Europe/Rome node --test tests/frontend/
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --screenshot=/tmp/card.png \
  --window-size=1180,2300 --virtual-time-budget=4000 "file://$PWD/tests/frontend/harness.html"
```
Prova dal vivo contro il portale, in un Home Assistant di prova con il recorder vero (credenziali dal
Portachiavi; stampa solo conteggi e differenze, mai consumi o codici):
```sh
PLENITUDE_LIVE=1 ~/venvs/ha-plenitude-test/bin/python -m pytest -s -p no:logging --tb=line tests/live
```

## Prototipo sul Mac

Ambiente (una volta):
```sh
/opt/homebrew/bin/python3.14 -m venv ~/venvs/ha-plenitude
~/venvs/ha-plenitude/bin/pip install -r requirements-dev.txt
```

Credenziali nel Portachiavi (una volta; la password viene chiesta senza mostrarla e non resta nella cronologia
della shell):
```sh
security add-generic-password -s ha-plenitude -a 'EMAIL-DELL-AREA-CLIENTI' -w
```

Uso:
```sh
~/venvs/ha-plenitude/bin/python scripts/prototipo.py login           # login, durata delle sessioni
~/venvs/ha-plenitude/bin/python scripts/prototipo.py stato           # le sessioni salvate valgono ancora?
~/venvs/ha-plenitude/bin/python scripts/prototipo.py consumi         # un giorno (due giorni fa)
~/venvs/ha-plenitude/bin/python scripts/prototipo.py consumi --giorno 2026-11-20 --valori
```

La sessione viene salvata in `~/.cache/ha-plenitude/sessione.json` con permessi `600`: contiene token e cookie,
quindi non va copiata né messa nel repository. Senza `--valori` lo script non stampa identificativi né consumi.

## Sessioni (misurate il 2026-11-22)
| Elemento | Durata | Rinnovo |
|---|---|---|
| `id_token` (JWT) | 60 s da `accounts.login`, 300 s da `accounts.getJWT` | si chiede quando serve |
| Sessione Gigya (`login_token`) | quella chiesta con `sessionExpiration`: 3000 s nella webapp; **30 giorni concessi** quando chiesti | con la password; tenuta reale a 30 giorni da misurare |
| Sessione del portale (`GYSESSION`, `G-GENUI`) | cookie validi 24 h (`Max-Age=86400`), ma il server la chiude prima: dopo **meno di 55 minuti di inattività** risponde `HTTP 406` | **senza password**, con `getJWT` + `getJwe`, finché la sessione Gigya vale (provato il 2026-11-22) |
