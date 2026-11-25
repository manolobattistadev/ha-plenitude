# Eni Plenitude per Home Assistant

[![Marketplace e HACS: repository personalizzato](https://img.shields.io/badge/Marketplace%20%7C%20HACS-custom%20repository-41BDF5)](#installazione)
[![Home Assistant 2026.9+](https://img.shields.io/badge/Home%20Assistant-2026.9%2B-18BCF2)](https://www.home-assistant.io/)
[![Test](https://github.com/paoloaq/ha-plenitude/actions/workflows/tests.yml/badge.svg)](https://github.com/paoloaq/ha-plenitude/actions/workflows/tests.yml)
[![Licenza: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[English](README.md) · **Italiano**

Un'integrazione di Home Assistant che porta in Home Assistant i consumi di luce della tua area clienti
[Eni Plenitude](https://eniplenitude.com):

- i consumi orari come **statistiche storiche**, con la loro data reale, pronti per la dashboard Energia;
- gli stessi consumi divisi per **fascia ARERA** (F1, F2, F3);
- le **categorie stimate** dell'area clienti (comfort ambientale, lavare, cucinare…), giorno per giorno;
- il **costo**, dai prezzi che inserisci (prezzo unico, due o tre fasce) più **tutti gli altri costi che vuoi**
  (mensili, bimestrali, annuali, per kW, per kWh o in percentuale: canone RAI, quota fissa, quota potenza, oneri di
  sistema, IVA…);
- due **card** per le dashboard: il grafico dei consumi con il periodo che preferisci e la **bolletta in corso**
  (kWh ed euro del periodo di fatturazione finora, con una stima a fine periodo).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-dark-it.png">
  <img alt="La plancia d'esempio: bolletta in corso e consumi della settimana in euro, per fascia (consumi sintetici)" src="https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-light-it.png">
</picture>

È un'integrazione, non un add-on: funziona con ogni tipo di installazione (Home Assistant OS, Container, Core).

> [!IMPORTANT]
> **Non ufficiale.** Questo progetto non è affiliato, approvato o supportato da Eni Plenitude o da Eni. Usa gli
> stessi servizi web dell'area clienti, che non sono documentati e possono cambiare senza preavviso. Fa poche
> richieste al giorno, come una persona che controlla l'area clienti.

> [!NOTE]
> **Sviluppato con l'AI.** Questo software è sviluppato con un forte aiuto di agenti AI di programmazione,
> mentre una persona guida le idee, le scelte di progetto, le prove su un'area clienti reale e il debug. È
> dichiarato apertamente perché ha determinato il modo in cui il progetto è stato costruito. Se il codice
> sviluppato con l'AI non ti convince, questo software non fa per te.
>
> *— semicit. del grande [antirez](https://github.com/antirez)*

## Indice
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Configurazione](#configurazione)
- [Cosa ottieni](#cosa-ottieni)
- [Card](#card)
- [Come funziona](#come-funziona)
- [Lingue](#lingue)
- [Privacy e sicurezza](#privacy-e-sicurezza)
- [Problemi frequenti](#problemi-frequenti)
- [Rimozione](#rimozione)
- [Limiti](#limiti)
- [Sviluppo](#sviluppo)

## Requisiti
- Home Assistant **2026.9** o successivo.
- Un account dell'area clienti Eni Plenitude con **email e password** (l'accesso con account social non è
  supportato).
- Una fornitura di **luce** per cui l'area clienti mostra l'analisi dei consumi (consumi ogni 15 minuti, di solito
  disponibili con i contatori elettronici di seconda generazione). Il gas non è ancora supportato.

## Installazione

Dipende dalla versione di Home Assistant: dalla **2026.11** HACS fa parte di Home Assistant come **Marketplace**;
fino alla 2026.10 è l'integrazione personalizzata HACS.

### Con il Marketplace (Home Assistant 2026.11 e successive, consigliata)
1. Apri **Impostazioni → Marketplace**, scheda **Aggiungi dal collegamento**. Oppure apri [questo link](https://my.home-assistant.io/redirect/marketplace_repository/?owner=paoloaq&repository=ha-plenitude&category=integration):
   chiede di aggiungere il repository al Marketplace del tuo Home Assistant.
2. In **Collegamento GitHub** inserisci `https://github.com/paoloaq/ha-plenitude`, come **Tipo** scegli
   **Integrazione**, poi seleziona **Aggiungi**. La prima volta il Marketplace chiede di collegare GitHub
   (**Collega GitHub**): ricevi un codice da inserire su GitHub, e il collegamento legge solo informazioni pubbliche.
3. Cerca **Eni Plenitude**, aprila e scegli **Installa**.
4. Riavvia Home Assistant.

L'avevi installata con HACS prima di aggiornare Home Assistant alla 2026.11? Non devi fare niente: al primo avvio il
Marketplace prende in carico HACS e i repository aggiunti, Eni Plenitude compresa.

### Con HACS (Home Assistant 2026.10 e precedenti)
1. In Home Assistant apri **HACS**, poi il menu **⋮ → Repository personalizzati**.
2. Aggiungi `https://github.com/paoloaq/ha-plenitude` con tipo **Integrazione**.
3. Cerca **Eni Plenitude**, aprila e scegli **Scarica**.
4. Riavvia Home Assistant.

### A mano
1. Scarica l'[ultima versione](https://github.com/paoloaq/ha-plenitude/releases/latest) e copia la cartella
   `custom_components/plenitude` nella cartella `custom_components` della configurazione di Home Assistant (quella
   che contiene `configuration.yaml`; con Docker, la cartella montata su `/config`).
2. Riavvia Home Assistant.

## Configurazione
1. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Eni Plenitude**.
2. Inserisci email e password dell'area clienti.
3. Se nell'account ci sono più forniture luce, scegli quella da importare. Per importarne un'altra, aggiungi di
   nuovo l'integrazione.

Il primo import parte subito, in background: legge lo storico all'indietro da ieri, tre giorni alla volta, finché
trova un mese senza dati (al massimo tre anni). Le ultime due settimane compaiono in pochi secondi; il resto dello
storico arriva in qualche minuto (circa 6 minuti per tre anni).

### Prezzi e costi
Plenitude non espone il prezzo della tua offerta, quindi il costo si calcola dai prezzi e dai costi che inserisci.

**Prezzo dell'energia.** Apri **Impostazioni → Dispositivi e servizi → Eni Plenitude → Configura**:

| Tipo di prezzo | Campi |
|---|---|
| Nessun prezzo | solo consumi |
| Prezzo unico (monoraria) | un prezzo per kWh uguale in tutte le ore |
| Due fasce (bioraria) | F1 e F23 (F2 + F3) |
| Tre fasce (multioraria) | F1, F2 e F3 |

**Altri costi.** Nella stessa pagina scegli **Aggiungi costo**, tutte le volte che serve. Prima indichi del costo:
- **Nome**: un testo libero, per esempio canone RAI, quota fissa, quota potenza, oneri di sistema, IVA;
- **Tipologia**: mensile, bimestrale, annuale, €/kW al mese, per kWh o percentuale.

Poi, nell'unità della tipologia:
- **Importo**: euro, euro per kWh, euro per kW o percentuale, con la virgola o il punto per i decimali (`9,15` o
  `9.15`), al massimo 6 decimali, senza separatori delle migliaia. Per uno sconto usa un importo negativo. Lo
  stesso vale per i prezzi.
- **Potenza**, solo per i costi in €/kW al mese (la quota potenza della bolletta): la potenza del contratto in kW,
  come in bolletta (potenza impegnata). Se l'area clienti la indica, è già proposta.
- **Escluso dalle percentuali**, per tutte le tipologie tranne le percentuali: attivalo per un costo che non paga
  l'IVA, come il canone TV.

I costi sono elencati sotto l'integrazione, dove puoi modificarli o eliminarli.

Come vengono contati:
- I costi **per kWh** si aggiungono al prezzo di ogni ora: sono nella statistica del costo, nella dashboard
  Energia, nel sensore e nelle card. Quando cambiano i prezzi, i costi per kWh o le percentuali, il costo di tutto
  lo storico viene ricalcolato.
- I costi **mensili, bimestrali, annuali e in €/kW al mese** non dipendono dalle ore, quindi **non** sono nella
  statistica del costo né nella dashboard Energia. Le card li contano **per intero, come inseriti**: ogni mese
  porta 1/12 dei loro euro all'anno (importo × 12 per i mensili, × 6 per i bimestrali, × 1 per gli annuali,
  × potenza × 12 per i costi in €/kW al mese), diviso tra i suoi giorni, dal mese del primo giorno con dati al mese
  dell'ultimo. Un mese mostra il suo importo intero anche se non è finito. La card della bolletta in corso conta
  tutti i mesi del periodo, anche prima che finisca (un canone TV di 9 euro al mese vale 18 euro in una bolletta
  bimestrale), ed elenca ogni costo.
- Le **percentuali** (per esempio l'IVA) si applicano al prezzo dell'energia e a tutti gli altri costi non esclusi:
  alle ore nella statistica del costo, nella dashboard Energia e nel sensore, ai costi periodici nelle card. La card
  della bolletta in corso mostra ognuna su una riga a sé. Più percentuali si sommano e non si applicano l'una
  all'altra (10% e 2% fanno 12%).

**Avvicinarsi alla bolletta.** Come prezzo usa quello dell'energia della tua offerta, poi aggiungi come costi le
altre voci di una bolletta, senza IVA: trasporto, oneri di sistema e accise per kWh; quota fissa e canone RAI come
costi periodici; la quota potenza come costo in €/kW al mese. Poi aggiungi l'IVA come percentuale (10% per le
abitazioni) ed escludi il canone RAI.

## Cosa ottieni

### Statistiche
L'integrazione importa statistiche storiche con sorgente `plenitude`. Negli identificativi `<p>` è
`plenitude:luce_<chiave>`, dove la chiave è un hash corto del POD della fornitura.

| Statistica | Unità | Contenuto |
|---|---|---|
| `<p>_consumo` | kWh | consumo misurato, ora per ora |
| `<p>_f1`, `<p>_f2`, `<p>_f3` | kWh | lo stesso consumo diviso per fascia ARERA (0 nelle ore delle altre fasce) |
| `<p>_costo` | EUR | kWh × (prezzo della fascia + costi per kWh), con le percentuali; con un prezzo o un costo (costi periodici esclusi) |
| `<p>_cat_<categoria>` | kWh | la ripartizione **stimata** dell'area clienti, un valore al giorno |

Categorie: `comfort_ambientale`, `standby`, `lavare`, `elettronica_luci`, `refrigerare`, `cucinare`,
`ricarica_elettrica`, `altro`.

I nomi delle statistiche seguono la lingua del server, per esempio *Plenitude luce consumo* o *Plenitude
electricity consumption*.

### Sensori
| Sensore | Contenuto |
|---|---|
| Ultimo giorno disponibile | il giorno più recente con dati |
| Consumo dell'ultimo giorno | kWh di quel giorno |
| Costo dei consumi dell'ultimo giorno | euro di quel giorno: energia e costi per kWh con le percentuali, senza costi periodici |

Mostrano a che punto è l'import. Non hanno `state_class` di proposito: la storia è nelle statistiche, con le date
giuste.

### Dashboard Energia
1. **Impostazioni → Dashboard → Energia → Rete elettrica → Aggiungi consumo.**
2. Come consumo scegli la statistica *Plenitude luce consumo* (*Plenitude electricity consumption* su un server in
   inglese).
3. Con un prezzo o dei costi, scegli **Usa un'entità che tiene traccia dei costi totali** e la statistica *Plenitude luce
   costo*.

Home Assistant non sa calcolare il costo delle statistiche importate a partire da un prezzo, quindi lo calcola
l'integrazione. I dati arrivano con circa due giorni di ritardo: gli ultimi due giorni restano vuoti finché
Plenitude non li pubblica.

## Card
L'integrazione porta con sé due card e le carica da sola in ogni dashboard: non vanno installate né aggiunte alle
risorse. In una dashboard scegli **Modifica → Aggiungi card**, cerca **Plenitude** e configurale dall'editor
visuale. Le card seguono la lingua del tuo profilo utente (italiano o inglese) e il tema chiaro o scuro.

### Plancia d'esempio
[`examples/dashboard.yaml`](examples/dashboard.yaml) è una plancia con entrambe le card: la bolletta in corso del
bimestre e i consumi della settimana in euro, per fascia. In **Impostazioni → Plance → Aggiungi plancia** scegli
**Nuova plancia da zero**; aprila, scegli **Modifica la plancia** (la matita), poi **⋮ → Editor di configurazione
testuale**, incollala e metti in `start_date` il primo giorno di un tuo periodo di fatturazione. Gli screenshot la
mostrano con consumi sintetici e con i prezzi e i costi di un contratto vero (prezzo unico, 6 kW), nel tema chiaro e
in quello scuro.

| Chiaro | Scuro |
|---|---|
| ![Plancia d'esempio, tema chiaro](https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-light-it.png) | ![Plancia d'esempio, tema scuro](https://raw.githubusercontent.com/paoloaq/ha-plenitude/main/docs/images/dashboard-dark-it.png) |

Le statistiche cambiano una volta al giorno, quando arrivano i giorni nuovi. Fino ad allora le card tengono quello
che hanno letto: in memoria per tutte le card della pagina e nella memoria del browser quando la pagina si ricarica
(pochi kB per periodo, al massimo 40 periodi). Tornare a una dashboard, o cambiare vista o unità su una card, non
rilegge le statistiche; i dati nuovi compaiono entro circa 5 minuti dal loro import.

### Consumi
Un grafico a colonne. Nelle impostazioni scegli periodo, vista e unità di partenza. Sulla card puoi cambiarli,
spostarti avanti e indietro e tornare agli ultimi dati. Passa sopra o tocca una colonna per vederne i valori;
**Tabella** li mostra tutti.

```yaml
type: custom:plenitude-consumption-card
period: month      # day | week | month | year (giorno, settimana, mese, anno)
view: bands        # total | bands | categories (totale, fasce, categorie)
unit: kwh          # kwh | eur
```

- Le **categorie** sono stime giornaliere: non ci sono nella vista del giorno e solo in kWh.
- **In euro**, i costi periodici (mensili, bimestrali, annuali, €/kW al mese), con le loro percentuali, sono il
  segmento grigio alla base delle colonne.

### Bolletta in corso
Consumo e costo dall'inizio del periodo di fatturazione in corso all'ultimo giorno con dati. Mostra anche:
- la ripartizione per fascia;
- l'avanzamento del periodo;
- la composizione del costo: energia, poi ogni costo che hai inserito, poi ogni percentuale;
- una stima a fine periodo (media dei giorni con dati × durata del periodo, più i costi periodici dell'intero
  periodo);
- le colonne giorno per giorno.

Con le frecce vedi i periodi passati, da confrontare con le bollette.

```yaml
type: custom:plenitude-billing-card
start_date: "2026-11-01"   # primo giorno di un qualsiasi periodo di fatturazione (lo leggi su una bolletta)
months: 2                  # 2 = bimestre, 1 = mese
```

I periodi si ripetono ogni `months` mesi da `start_date`. Se la data di inizio è il 31, i mesi più corti finiscono
all'ultimo giorno.

Entrambe accettano anche `title` ed `entry` (la voce di configurazione, quando hai più forniture).

## Come funziona
- **Sessione.** Al primo accesso l'integrazione chiede a Plenitude una sessione di 30 giorni. La sessione
  dell'area clienti scade dopo meno di un'ora di inattività e viene riaperta con quella di 30 giorni, senza
  password. La password si usa di nuovo solo quando la sessione di 30 giorni è finita. Se Plenitude la rifiuta,
  Home Assistant ti chiede di accedere di nuovo in **Impostazioni → Dispositivi e servizi**.
- **Aggiornamenti.** Ogni 6 ore l'integrazione chiede i giorni nuovi (i dati arrivano con circa due giorni di
  ritardo). Una volta al giorno chiede di nuovo anche i giorni delle ultime due settimane rimasti senza dati, nel
  caso arrivino in ritardo.
- **Cambio dell'ora.** Nei giorni del cambio gli orari si ricostruiscono dalla posizione dei valori, perché il
  server li etichetta male. Un giorno con un numero di valori diverso dalla sua durata viene saltato.
- **Fasce ARERA** ([delibera 181/06](https://www.arera.it/atti-e-provvedimenti/dettaglio/06/181-06),
  tabella 1):
  - F1: dal lunedì al venerdì 8-19;
  - F2: dal lunedì al venerdì 7-8 e 19-23, il sabato 7-23;
  - F3: notti 23-7, domeniche e festivi.

  Festivi: 1 e 6 gennaio, lunedì di Pasqua, 25 aprile, 1 maggio, 2 giugno, 15 agosto, 1 novembre, 8, 25 e
  26 dicembre. Il 4 ottobre (di nuovo festa nazionale dal 2026) non è nella tabella ARERA ed è trattato come giorno
  feriale.

## Lingue
Italiano e inglese; ogni altra lingua usa l'inglese.

| Cosa | Segue |
|---|---|
| Configurazione, opzioni, costi, errori nei form, stati (*sconosciuto*), formato dei numeri | la lingua del profilo di ciascun utente |
| Card | la lingua del profilo di ciascun utente |
| Nomi delle entità | la lingua del server |
| Nomi delle statistiche, titolo della voce, modello del dispositivo | la lingua del server quando vengono creati |

Se alcuni testi sono in italiano e altri in inglese, la lingua del server (**Impostazioni → Sistema → Generale**) e
quella del tuo profilo (il tuo nome in fondo alla barra laterale → **Lingua**) sono diverse: impostale entrambe.

## Privacy e sicurezza
- **Credenziali.** Email e password restano nella voce di configurazione, come per ogni integrazione che accede a
  un servizio. Vengono inviate solo al servizio di accesso di Plenitude (`login.eniplenitude.com`).
- **Sessione.** Token e cookie stanno in `.storage/plenitude.<id della voce>`, leggibile solo dal proprietario del
  file.
- **Nessun'altra destinazione.** L'integrazione parla solo con `eniplenitude.com` e `login.eniplenitude.com`,
  senza statistiche d'uso né telemetria. Le card leggono le statistiche solo dal tuo Home Assistant.
- **POD.** Il POD della fornitura non viene salvato: statistiche ed entità usano un suo hash corto. L'hash non è
  un segreto (dal POD si risale per tentativi), quindi non pubblicare gli identificativi delle tue statistiche.
- **Diagnostica.** *Scarica diagnostica* toglie credenziali, token, POD, chiave della fornitura, indirizzo e
  valori di consumo: puoi allegarla a una segnalazione.

Per segnalare una vulnerabilità vedi [SECURITY.md](SECURITY.md).

## Problemi frequenti
- **Log di debug.** Nella pagina dell'integrazione scegli **Abilita la registrazione di debug**, riproduci il
  problema, poi disabilitala per scaricare il log. Oppure in `configuration.yaml`:
  ```yaml
  logger:
    logs:
      custom_components.plenitude: debug
  ```
  L'integrazione non scrive credenziali né token nel log; leggilo comunque prima di condividerlo.

  Se il problema avviene mentre aggiungi l'integrazione (quindi la sua pagina non esiste ancora), accendi il log
  di debug da **Strumenti per sviluppatori → Azioni** con l'azione `logger.set_level` e i dati
  `custom_components.plenitude: debug`, poi riprova. Ogni richiesta viene scritta con il suo stato HTTP; i codici
  del conto sono mascherati.
- **"Plenitude ha rifiutato il login".** La password è cambiata, o Plenitude chiede una verifica aggiuntiva.
  Accedi all'area clienti con un browser, poi apri la richiesta di nuovo accesso in **Impostazioni → Dispositivi
  e servizi** e inserisci la password.
- **"L'area clienti rifiuta i dati del conto".** Aggiorna alla 0.3.5 o successiva: con Home Assistant 2026.9 le
  versioni precedenti perdevano i cookie di sessione (vedi [docs/protocol.md](docs/protocol.md)). Se succede
  ancora, controlla che l'area clienti funzioni da un browser, accendi il log di debug e apri una segnalazione.
  Una volta configurata, l'integrazione rifà il login da sola, al massimo ogni 15 minuti.
- **Mancano alcuni giorni.** A volte l'area clienti stessa non ha i dati di alcuni giorni. L'integrazione chiede
  di nuovo i giorni mancanti delle ultime due settimane, una volta al giorno.
- **Dopo la prima configurazione i sensori restano *sconosciuto*.** Il primo import è ancora in corso: le ultime
  due settimane compaiono in pochi secondi, il resto in qualche minuto (nel log: *Plenitude: first import, …*).
- **Le card non compaiono** in *Aggiungi card*, o una dashboard mostra *Custom element doesn't exist:
  plenitude-…-card*. L'integrazione aggiunge le card quando Home Assistant si avvia, e il frontend le legge solo
  quando la pagina si carica: una pagina caricata mentre Home Assistant si stava avviando non le ha. Ricarica la
  pagina ad avvio finito (senza cache, o svuota la cache dell'app). Se mancano ancora, apri
  `/plenitude_static/plenitude-cards.js` sul tuo Home Assistant: deve mostrare il codice delle card con la versione
  in cima. Non aggiungere le card alle risorse della dashboard: le carica l'integrazione.
  Le versioni precedenti alla 0.5.2 potevano perdere le card a caso con Home Assistant 2026.10 e precedenti, anche
  ore dopo un riavvio (il frontend sostituiva il suo registro degli elementi dopo che le card erano state definite):
  aggiorna l'integrazione. Nella console del browser `customElements.get("plenitude-billing-card")` non deve
  restituire `undefined`.
- **Il costo è diverso dalla bolletta.** Vedi [Prezzi e costi](#prezzi-e-costi): inserisci ogni voce della
  bolletta come costo, senza IVA, e l'IVA come percentuale. Le bollette possono contenere anche conguagli e letture
  stimate.

## Rimozione
1. **Impostazioni → Dispositivi e servizi → Eni Plenitude → ⋮ → Elimina.**
2. Le statistiche importate restano nel database. Per eliminarle vai in **Strumenti per sviluppatori →
   Statistiche**, cerca `plenitude` ed eliminale.
3. Nel Marketplace (o in HACS fino a Home Assistant 2026.10) apri **Eni Plenitude** e scegli **Disinstalla**, poi
   riavvia Home Assistant.

## Limiti
- Le statistiche di Home Assistant sono orarie: i valori ogni 15 minuti si sommano per ora.
- Le categorie sono stime di Plenitude e arrivano solo giorno per giorno.
- I valori mensili per fascia dell'area clienti non sono usati: non coincidono con i mesi di calendario (sembrano
  periodi di lettura o di fatturazione).
- Il costo è una stima dai prezzi, dai costi e dalle percentuali che inserisci: le bollette contengono anche
  conguagli e letture stimate che l'integrazione non può conoscere.
- Solo luce; il gas non è ancora supportato.

## Sviluppo
Vedi [CONTRIBUTING.md](CONTRIBUTING.md) (in inglese): struttura del codice, test sulla versione minima e
sull'ultima di Home Assistant, pagina di prova delle card e pubblicazione di una versione. Le note sui servizi web
dell'area clienti sono in [docs/protocol.md](docs/protocol.md). Le modifiche sono elencate in
[CHANGELOG.md](CHANGELOG.md).

## Licenza
[MIT](LICENSE). *Eni Plenitude* e *Plenitude* sono marchi dei rispettivi proprietari e sono citati solo per dire
con quale servizio funziona l'integrazione.
