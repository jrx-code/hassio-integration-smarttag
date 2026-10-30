#!/usr/bin/env python3
"""PoC: co API SmartThings mówi o Twoich SmartTagach.

Użycie:
    export SMARTTHINGS_TOKEN=...   # PAT z https://account.smartthings.com/tokens
    python3 tools/st_probe.py              # podsumowanie tagów
    python3 tools/st_probe.py --raw DIR    # zapis surowych JSON-ów (zredagowanych)
    python3 tools/st_probe.py --pool       # test generowania puli privacy ID

Skrypt NIGDY nie wypisuje tokenu ani encryptionKey. Pliki z --raw są
redagowane, ale i tak nie commituj ich do repo (katalog jest w .gitignore).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "smarttag"))

import cloud  # noqa: E402

SECRET_KEYS = {"encryptionKey", "privacyIdSeed", "privacyIdInitialVector", "requesterToken"}


def redact(obj):
    """Zamienia wartości wrażliwych pól na znacznik."""
    if isinstance(obj, dict):
        return {k: ("<REDACTED>" if k in SECRET_KEYS and v else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def get(url: str, token: str) -> tuple[int, dict | None]:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as err:
        body = err.read()
        try:
            return err.code, json.loads(body)
        except ValueError:
            return err.code, {"raw": body.decode(errors="replace")[:300]}


def paged(url: str, token: str) -> list[dict]:
    items: list[dict] = []
    while url:
        status, data = get(url, token)
        if status != 200 or not data:
            print(f"! {url} -> HTTP {status}: {data}", file=sys.stderr)
            break
        items.extend(data.get("items", []))
        url = ((data.get("_links") or {}).get("next") or {}).get("href")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, help="zapisz zredagowane JSON-y do katalogu")
    parser.add_argument("--pool", action="store_true", help="spróbuj wygenerować pulę privacy ID")
    args = parser.parse_args()

    token = os.environ.get("SMARTTHINGS_TOKEN")
    if not token:
        print("Ustaw zmienną SMARTTHINGS_TOKEN (PAT SmartThings).", file=sys.stderr)
        return 2

    devices = paged(f"{cloud.API_BASE}/devices", token)
    tags = [d for d in devices if cloud.is_tag(d)]
    print(f"Urządzeń: {len(devices)}, w tym tagów: {len(tags)}\n")
    if args.raw:
        args.raw.mkdir(parents=True, exist_ok=True)

    for dev in tags:
        dev_id = dev["deviceId"]
        status, detail = get(f"{cloud.API_BASE}/devices/{dev_id}", token)
        detail = detail if status == 200 and detail else dev
        info = cloud.parse_tag(detail)
        _, st = get(f"{cloud.API_BASE}/devices/{dev_id}/status", token)
        geo = (((st or {}).get("components") or {}).get("main") or {}).get("geolocation") or {}
        lat = (geo.get("latitude") or {}).get("value")
        print(f"== {info.label} ({dev_id})")
        print(f"   model: {info.model}")
        print(f"   capabilities: {', '.join(info.capabilities) or '-'}")
        print(f"   bleD2D: {info.has_ble_d2d}, materiał do puli privacy ID: {info.has_privacy_material}")
        print(f"   bateria: {info.battery} (aktualizacja {info.battery_updated})")
        print(
            f"   ostatnie połączenie: {info.connected_device} {info.d2d_status} "
            f"nearby={info.nearby} o {info.last_connection}"
        )
        print(f"   searchingStatus: {info.searching_status}")
        print(f"   geolocation.latitude ze /status: {lat!r}")
        if args.pool:
            try:
                import privacy
            except ImportError:
                print("   pula: brak modułu cryptography (pip install cryptography)")
            else:
                pool = privacy.pool_from_device(detail)
                print(f"   pula privacy ID: {len(pool) if pool else 'niedostępna'}")
        if args.raw:
            (args.raw / f"{dev_id}.device.json").write_text(json.dumps(redact(detail), indent=2))
            (args.raw / f"{dev_id}.status.json").write_text(json.dumps(redact(st), indent=2))
        print()

    apps = paged(f"{cloud.API_BASE}/installedapps?allowed=true", token)
    fme = cloud.find_fme_installed_app(apps)
    print(f"InstalledApp SmartThings Find (FME): {'jest' if fme else 'brak / brak uprawnień'}")
    print(
        "Uwaga: endpoint /installedapps/{id}/execute z /trackers/geolocation wymaga tokenu"
        " konta Samsung (OAuth aplikacji SmartThings), nie PAT. Patrz docs/RESEARCH.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
