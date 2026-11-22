#!/usr/bin/env python3
"""Prototipo da Mac per l'area clienti Plenitude: login, durata delle sessioni, consumi quartorari.

Credenziali: Portachiavi di macOS, servizio "ha-plenitude" (vedi README).
Sessione: ~/.cache/ha-plenitude/sessione.json, leggibile solo dall'utente (contiene token e cookie).
Senza --valori non stampa né identificativi né consumi: solo esiti, durate e conteggi.

Comandi:
  login   [--durata SECONDI]          login completo con le credenziali, salva la sessione
  stato                               controlla, senza password, se la sessione salvata vale ancora
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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "plenitude"))
import api  # noqa: E402  (modulo condiviso con l'integrazione, senza dipendenze da Home Assistant)

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
        capture_output=True, text=True, check=True,
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
    return f"{(datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 60:.0f} minuti"


def nuova_sessione_http() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(), timeout=aiohttp.ClientTimeout(total=60))


async def fai_login(client: api.PlenitudeClient, durata: int) -> None:
    email, password = credenziali()
    durate = await client.login(email, password, session_expiration=durata)
    print(f"Login Gigya riuscito. Sessione Gigya: {durate['gigya_session']} s "
          f"(chiesti {durate['requested_gigya_session']} s); JWT: {durate['jwt']} s.")
    print("Sessione del portale aperta (cookie GYSESSION e G-GENUI presenti).")
    salva_stato(client, {"login_at": datetime.now(timezone.utc).isoformat(),
                         "portal_opened_at": datetime.now(timezone.utc).isoformat()})


async def cmd_login(args: argparse.Namespace) -> None:
    async with nuova_sessione_http() as http:
        client = api.PlenitudeClient(http)
        await fai_login(client, args.durata)
        conto = await client.get_account()
        forniture = await client.get_supplies(conto)
        print(f"Conto trovato. Forniture: {len(forniture)} "
              f"({', '.join(f.kind for f in forniture)}); dati per l'analisi dei consumi: "
              f"{'sì' if all(f.contract_id and f.house_id for f in forniture) else 'mancano'}.")
        salva_stato(client)


async def cmd_stato(args: argparse.Namespace) -> None:
    stato = leggi_stato()
    if not stato:
        sys.exit("Nessuna sessione salvata: lancia prima il comando login.")
    print(f"Ultimo login: {minuti_da(stato.get('login_at'))} fa; "
          f"sessione del portale aperta {minuti_da(stato.get('portal_opened_at'))} fa.")
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
            print(f"Sessione Gigya (login_token): VALIDA, rilascia JWT da {jwt} s. Scadenza dichiarata: "
                  f"{client.login_token_expires_at:%d/%m %H:%M} UTC.")
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
        salva_stato(client, {"portal_opened_at": datetime.now(timezone.utc).isoformat()})
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
    print(f"Giorno {giorno:%d/%m/%Y}: stato {dati.status}; {len(h)} valori orari, {len(q)} quarti d'ora.")
    if not q:
        print("Nessun quarto d'ora: il giorno potrebbe non essere ancora disponibile.")
        return
    giorni = {r.start.date() for r in q}
    somma_q, somma_h = sum(r.kwh for r in q), sum(r.kwh for r in h)
    print(f"Primo {q[0].start:%d/%m %H:%M}, ultimo {q[-1].start:%d/%m %H:%M} (ora italiana); "
          f"giorno restituito = giorno chiesto: {'sì' if giorni == {giorno} else f'NO {sorted(giorni)}'}; "
          f"somma quarti d'ora = somma ore: {'sì' if abs(somma_q - somma_h) < 0.01 else 'NO'}.")
    if args.valori:
        print(f"\nTotale del giorno: {somma_q:.3f} kWh")
        for ora in h:
            print(f"  {ora.start:%H:%M}  {ora.kwh:7.3f} kWh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--durata", type=int, default=3000,
                        help="durata della sessione Gigya da chiedere al login, in secondi (la webapp usa 3000)")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("login")
    sub.add_parser("stato")
    p = sub.add_parser("consumi")
    p.add_argument("--giorno", help="AAAA-MM-GG (predefinito: due giorni fa)")
    p.add_argument("--valori", action="store_true", help="stampa anche i consumi orari (dati personali)")
    args = parser.parse_args()
    comandi = {"login": cmd_login, "stato": cmd_stato, "consumi": cmd_consumi}
    try:
        asyncio.run(comandi[args.comando](args))
    except api.PlenitudeAuthError as err:
        sys.exit(f"Login rifiutato da Gigya: {err}")
    except api.PlenitudeError as err:
        sys.exit(f"Errore: {err}")


if __name__ == "__main__":
    main()
