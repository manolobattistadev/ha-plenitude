# ha-plenitude

Integrazione personalizzata di Home Assistant per i consumi di luce (e in futuro gas) dell'area clienti
[Eni Plenitude](https://eniplenitude.com/my-eni). Le credenziali si inseriscono una volta nella configurazione
dell'integrazione. I consumi quartorari vengono importati come statistiche storiche, visibili nei grafici e
nella dashboard Energia. Funziona con ogni tipo di installazione di Home Assistant (OS, Container, Core).

> **API non ufficiali.** Le chiamate sono state ricostruite il 2026-11-22 dal traffico della webapp e possono
> cambiare senza preavviso. Uso personale, una sincronizzazione al giorno.

## Stato
- [x] Analisi delle API (login Gigya, sessione del portale, consumi quartorari, mensili per fascia)
- [x] Client asincrono indipendente da Home Assistant: `custom_components/plenitude/api.py`
- [x] Prototipo provato dal Mac (2026-11-22): login da script senza CAPTCHA, quarti d'ora di un giorno
- [x] Portale scaduto dopo meno di 55 minuti di inattività (`406`), rinnovato senza password (2026-11-22)
- [ ] Tenuta della sessione Gigya di 30 giorni oltre le 24 ore (`prototipo.py stato` nei prossimi giorni)
- [ ] Integrazione: configurazione guidata, ri-autenticazione, import delle statistiche, HACS

## Comportamento dei dati (verificato il 2026-11-22)
- Storico quartorario dal **4 gennaio 2026**; i dati arrivano con circa **2 giorni** di ritardo.
- Ci sono **giorni mancanti** (`status: NO_DATA`), per esempio 1-3/01, 9 giorni di febbraio, 15/03 e
  25/10: l'integrazione deve saltarli senza interrompere la somma cumulativa.
- Il server usa solo la **data** di `startTime`, non l'ora.
- **Cambio d'ora:** il 29/03 il server restituisce 92 quarti d'ora (giusto) ma con etichette e timestamp
  spostati di un'ora dopo le 02:00. Il client ricostruisce gli orari dalla posizione (mezzanotte italiana +
  *i* × 15 minuti, in UTC) e scarta il giorno se il numero di valori non corrisponde alla durata del giorno.
  Il 25/10 (25 ore) manca del tutto.

## Struttura
```
custom_components/plenitude/api.py   client dell'area clienti (solo aiohttp, nessuna dipendenza da HA)
scripts/prototipo.py                 prova da riga di comando sul Mac
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
| Sessione Gigya (`login_token`) | quella chiesta con `sessionExpiration`: 3000 s nella webapp; **30 giorni concessi** quando chiesti dal prototipo (`--durata 2592000`) | con la password; tenuta reale a 30 giorni da misurare |
| Sessione del portale (`GYSESSION`, `G-GENUI`) | cookie validi 24 h (`Max-Age=86400`), ma il server la chiude prima: dopo **meno di 55 minuti di inattività** risponde `HTTP 406` | **senza password**, con `getJWT` + `getJwe`, finché la sessione Gigya vale (provato il 2026-11-22) |
