#!/usr/bin/env python3
"""Prototipo da Mac per l'area clienti Plenitude: login, durata delle sessioni, consumi quartorari.

Credenziali: Portachiavi di macOS, servizio "ha-plenitude" (vedi README).
Sessione: ~/.cache/ha-plenitude/sessione.json, leggibile solo dall'utente (contiene token e cookie).
Senza --valori non stampa né identificativi né consumi: solo esiti, durate e conteggi.

Comandi:
  login   [--durata SECONDI]          login completo con le credenziali, salva la sessione
  stato                               controlla, senza password, se la sessione salvata vale ancora
  gas     [--giorno AAAA-MM-GG] [--valori] [--salva FILE]
                                      sonda le risposte per la fornitura gas: struttura delle risposte (chiavi,
                                      tipi, lunghezze), valori mascherati se non si passa --valori
  consumi [--giorno AAAA-MM-GG] [--valori]
                                      scarica un giorno (predefinito: due giorni fa); riusa la sessione,
                                      la rinnova senza password o, se serve, rifà il login
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "plenitude"))
import api

SERVIZIO_PORTACHIAVI = "ha-plenitude"
FILE_STATO = Path.home() / ".cache" / "ha-plenitude" / "sessione.json"


def credenziali() -> tuple[str, str]:
    voce = subprocess.run(
        ["security", "find-generic-password", "-s", SERVIZIO_PORTACHIAVI], capture_output=True, text=True
    )
    trovato = re.search(r'"acct"<blob>="([^"]*)"', voce.stdout)
    if voce.returncode or not trovato:
        sys.exit(f"Credenziali non trovate nel Portachiavi (servizio {SERVIZIO_PORTACHIAVI}): vedi il README.")
    password = subprocess.run(
        ["security", "find-generic-password", "-s", SERVIZIO_PORTACHIAVI, "-w"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.rstrip("\n")
    return trovato.group(1), password


def salva_stato(client: api.PlenitudeClient, extra: dict | None = None) -> None:
    FILE_STATO.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stato = {**leggi_stato(), **client.export_state(), **(extra or {})}
    fd = os.open(FILE_STATO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(stato, f, indent=1)


def leggi_stato() -> dict:
    try:
        return json.loads(FILE_STATO.read_text())
    except FileNotFoundError:
        return {}


def minuti_da(iso: str | None) -> str:
    if not iso:
        return "?"
    return f"{(datetime.now(UTC) - datetime.fromisoformat(iso)).total_seconds() / 60:.0f} minuti"


def nuova_sessione_http() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(), timeout=aiohttp.ClientTimeout(total=60))


async def fai_login(client: api.PlenitudeClient, durata: int) -> None:
    email, password = credenziali()
    durate = await client.login(email, password, session_expiration=durata)
    print(
        f"Login Gigya riuscito. Sessione Gigya: {durate['gigya_session']} s "
        f"(chiesti {durate['requested_gigya_session']} s); JWT: {durate['jwt']} s."
    )
    print("Sessione del portale aperta (cookie GYSESSION e G-GENUI presenti).")
    salva_stato(client, {"login_at": datetime.now(UTC).isoformat(), "portal_opened_at": datetime.now(UTC).isoformat()})


async def cmd_login(args: argparse.Namespace) -> None:
    async with nuova_sessione_http() as http:
        client = api.PlenitudeClient(http)
        await fai_login(client, args.durata)
        conto = await client.get_account()
        forniture = await client.get_supplies(conto)
        print(
            f"Conto trovato. Forniture: {len(forniture)} "
            f"({', '.join(f.kind for f in forniture)}); dati per l'analisi dei consumi: "
            f"{'sì' if all(f.contract_id and f.house_id for f in forniture) else 'mancano'}."
        )
        salva_stato(client)


async def cmd_stato(args: argparse.Namespace) -> None:
    stato = leggi_stato()
    if not stato:
        sys.exit("Nessuna sessione salvata: lancia prima il comando login.")
    print(
        f"Ultimo login: {minuti_da(stato.get('login_at'))} fa; "
        f"sessione del portale aperta {minuti_da(stato.get('portal_opened_at'))} fa."
    )
    async with nuova_sessione_http() as http:
        client = api.PlenitudeClient(http)
        client.import_state(stato)
        try:
            await client.get_account()
            print("Sessione del portale (GYSESSION): VALIDA.")
        except api.PlenitudeSessionExpired as err:
            print(f"Sessione del portale (GYSESSION): SCADUTA ({err}).")
        try:
            jwt = await client.check_gigya_session()
            print(
                f"Sessione Gigya (login_token): VALIDA, rilascia JWT da {jwt} s. Scadenza dichiarata: "
                f"{client.login_token_expires_at:%d/%m %H:%M} UTC."
            )
        except api.PlenitudeSessionExpired as err:
            print(f"Sessione Gigya (login_token): SCADUTA ({err}).")


async def assicura_sessione(client: api.PlenitudeClient, durata: int) -> api.Account:
    """Riusa la sessione salvata; se è scaduta la rinnova senza password; se non si può, rifà il login."""
    client.import_state(leggi_stato())
    try:
        conto = await client.get_account()
        print("Sessione del portale riusata.")
        return conto
    except api.PlenitudeSessionExpired:
        pass
    try:
        await client.open_portal_session()
        salva_stato(client, {"portal_opened_at": datetime.now(UTC).isoformat()})
        print("Sessione del portale rinnovata SENZA password (sessione Gigya ancora valida).")
    except api.PlenitudeSessionExpired:
        print("Sessioni scadute: nuovo login con le credenziali del Portachiavi.")
        await fai_login(client, durata)
    return await client.get_account()


async def cmd_consumi(args: argparse.Namespace) -> None:
    giorno = date.fromisoformat(args.giorno) if args.giorno else date.today() - timedelta(days=2)
    async with nuova_sessione_http() as http:
        client = api.PlenitudeClient(http)
        conto = await assicura_sessione(client, args.durata)
        fornitura = next(f for f in await client.get_supplies(conto) if f.pod)
        salva_stato(client)
        dati = await client.get_day(conto, fornitura, giorno)
    q, h = dati.quarter_hours, dati.hours
    print(
        f"Giorno {giorno:%d/%m/%Y}: stato {dati.status}; {len(h)} valori orari, {len(q)} quarti d'ora; "
        f"timestamp del server corretti: {'sì' if dati.server_timestamps_ok else 'NO, ricostruiti dalla posizione'}."
    )
    if not q:
        print("Nessun quarto d'ora: giorno non ancora disponibile, mancante o con un numero di valori incoerente.")
        return
    giorni = {r.start.date() for r in q}
    somma_q, somma_h = sum(r.kwh for r in q), sum(r.kwh for r in h)
    print(
        f"Primo {q[0].start:%d/%m %H:%M}, ultimo {q[-1].start:%d/%m %H:%M} (ora italiana); "
        f"giorno restituito = giorno chiesto: {'sì' if giorni == {giorno} else f'NO {sorted(giorni)}'}; "
        f"somma quarti d'ora = somma ore: {'sì' if abs(somma_q - somma_h) < 0.01 else 'NO'}."
    )
    if args.valori:
        print(f"\nTotale del giorno: {somma_q:.3f} kWh")
        for ora in h:
            print(f"  {ora.start:%H:%M}  {ora.kwh:7.3f} kWh")


def forma(valore, valori: bool, profondita: int = 0) -> str:
    """Struttura di una risposta JSON: chiavi, tipi e lunghezze; i valori solo con --valori."""
    rientro = "  " * profondita
    if isinstance(valore, dict):
        righe = []
        for chiave, v in valore.items():
            if isinstance(v, (dict, list)):
                righe.append(f"{rientro}{chiave}:")
                righe.append(forma(v, valori, profondita + 1))
            else:
                righe.append(f"{rientro}{chiave}: {mostra(v, valori)}")
        return "\n".join(righe) or f"{rientro}{{}}"
    if isinstance(valore, list):
        if not valore:
            return f"{rientro}[] (vuota)"
        testa = f"{rientro}[{len(valore)} elementi] primo:"
        primo = valore[0]
        corpo = (
            forma(primo, valori, profondita + 1)
            if isinstance(primo, (dict, list))
            else f"{rientro}  {mostra(primo, valori)}"
        )
        return f"{testa}\n{corpo}"
    return f"{rientro}{mostra(valore, valori)}"


def mostra(v, valori: bool) -> str:
    if v is None or isinstance(v, bool):
        return repr(v)
    if valori:
        return repr(v)
    if isinstance(v, (int, float)):
        return type(v).__name__
    testo = str(v)
    return f"str({len(testo)})" if len(testo) > 3 else repr(testo)


async def sonda(client: api.PlenitudeClient, nome: str, metodo: str, percorso: str, args, **kw):
    chiavi = f"corpo chiavi {sorted(kw['body'])}" if "body" in kw else ""
    print(f"\n=== {nome}: {metodo} {api.safe_path(percorso)} {chiavi}")
    try:
        dati = await client._service(metodo, percorso, **kw)
    except api.PlenitudeError as err:
        print(f"  ERRORE: {err}")
        return None
    print(forma(dati, args.valori, 1))
    if args.salva:
        with open(args.salva, "a") as f:
            f.write(json.dumps({"nome": nome, "percorso": percorso, "corpo": kw.get("body"), "risposta": dati}) + "\n")
    return dati


async def cmd_gas(args: argparse.Namespace) -> None:
    giorno = date.fromisoformat(args.giorno) if args.giorno else date.today() - timedelta(days=3)
    async with nuova_sessione_http() as http:
        client = api.PlenitudeClient(http)
        conto = await assicura_sessione(client, args.durata)
        salva_stato(client)
        base = f"/api/profilo-energetico-services/{conto.account_code}"
        lista = await sonda(
            client, "lista forniture", "GET", f"/api/contiServices/conti/{conto.account_code}/lista-forniture", args
        )
        forniture = (lista or {}).get("fornitura", [])
        gas = [f for f in forniture if f.get("pdr")]
        luce = [f for f in forniture if f.get("pod")]
        print(f"\nForniture: {len(forniture)}, con PDR: {len(gas)}, con POD: {len(luce)}")
        if not gas:
            sys.exit("Nessuna fornitura gas (con PDR) nel conto.")
        pdr = gas[0]["pdr"]
        pod = luce[0]["pod"] if luce else ""
        profilo = await sonda(
            client,
            "profilo (pod+pdr)",
            "POST",
            f"{base}/users/{conto.client_code}/supplies",
            args,
            body={"pod": pod, "pdr": pdr},
        )
        if not pod:
            profilo = profilo or await sonda(
                client,
                "profilo (solo pdr)",
                "POST",
                f"{base}/users/{conto.client_code}/supplies",
                args,
                body={"pod": "", "pdr": pdr},
            )
        voci = (profilo or {}).get("fornitureClienteMidori4FE", [])
        candidati = [v for v in voci if pdr in json.dumps(v)] or [v for v in voci if v.get("lightCode") != pod]
        print(
            f"\nVoci del profilo: {len(voci)}; che contengono il PDR: {len([v for v in voci if pdr in json.dumps(v)])}"
        )
        if not candidati:
            print("Nessuna voce del profilo per il gas: provo con la voce della luce per vedere se ha campi gas.")
            candidati = voci
        for voce in candidati[:2]:
            contratto, casa = voce.get("contractId"), voce.get("houseId")
            for chiave in voce:
                if "gas" in chiave.lower() or "pdr" in chiave.lower() or "commodity" in chiave.lower():
                    print(f"  campo gas nella voce: {chiave}")
            if contratto is None:
                continue
            for vista, periodo in (
                (api.VIEW_DAY, api.day_period(giorno)),
                ("1", api.day_period(giorno - timedelta(days=6)) | {"endTime": api.day_period(giorno)["endTime"]}),
                (api.VIEW_MONTH, api.month_period(giorno.year, giorno.month)),
                (
                    api.VIEW_YEAR,
                    {
                        "startTime": api.month_period(giorno.year, 1)["startTime"],
                        "endTime": api.month_period(giorno.year, 12)["endTime"],
                    },
                ),
            ):
                corpo = {
                    "clientCode": conto.client_code,
                    "contractId": str(contratto),
                    "houseId": str(casa),
                    **periodo,
                    "type": vista,
                }
                await sonda(client, f"consumi vista {vista}", "POST", f"{base}/analysis/consumptions", args, body=corpo)
                await asyncio.sleep(0.4)
        await sonda(
            client,
            "consumptionData",
            "GET",
            "/api/consumptionData",
            args,
            params={"codiceContoCliente": conto.account_code},
        )
        salva_stato(client)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--durata",
        type=int,
        default=3000,
        help="durata della sessione Gigya da chiedere al login, in secondi (la webapp usa 3000)",
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("login")
    sub.add_parser("stato")
    p = sub.add_parser("consumi")
    p.add_argument("--giorno", help="AAAA-MM-GG (predefinito: due giorni fa)")
    p.add_argument("--valori", action="store_true", help="stampa anche i consumi orari (dati personali)")
    p = sub.add_parser("gas")
    p.add_argument("--giorno", help="AAAA-MM-GG (predefinito: tre giorni fa)")
    p.add_argument("--valori", action="store_true", help="stampa anche codici e consumi (dati personali)")
    p.add_argument("--salva", help="aggiunge le risposte grezze a questo file JSONL (dati personali)")
    args = parser.parse_args()
    comandi = {"login": cmd_login, "stato": cmd_stato, "consumi": cmd_consumi, "gas": cmd_gas}
    try:
        asyncio.run(comandi[args.comando](args))
    except api.PlenitudeAuthError as err:
        sys.exit(f"Login rifiutato da Gigya: {err}")
    except api.PlenitudeError as err:
        sys.exit(f"Errore: {err}")


if __name__ == "__main__":
    main()
