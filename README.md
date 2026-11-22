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
- [ ] Prototipo provato dal Mac: login, durata delle sessioni, un giorno di quarti d'ora
- [ ] Integrazione: configurazione guidata, ri-autenticazione, import delle statistiche, HACS

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
| Sessione Gigya (`login_token`) | 3000 s, il valore chiesto dalla webapp | con la password; da provare se Gigya concede durate più lunghe |
| Sessione del portale (`GYSESSION`, `G-GENUI`) | cookie validi 24 h (`Max-Age=86400`); scadenza reale da misurare | senza password finché la sessione Gigya vale |
