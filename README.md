# SmartTag dla Home Assistant

Własna integracja dla Samsung Galaxy SmartTag (gen 1, SmartTag+ i SmartTag2).
Cel: z tagów, które we wbudowanej integracji SmartThings nie mają żadnych encji,
zrobić w HA obecność, baterię i (opcjonalnie) położenie GPS.

> Status: wczesny etap. Na `main` jest research, biblioteka (parser BLE, pula
> privacy ID, parser API) z testami i skrypt PoC. Integracja HA powstaje na
> gałęziach z PR.

## Skąd problem

Integracja SmartThings w HA nie tworzy encji dla tagów celowo: API SmartThings
zwraca dla tagów same `null` (także lokalizację), więc od 2025 r. HA dodaje tylko
urządzenie. Szczegóły i źródła: [docs/RESEARCH.md](docs/RESEARCH.md).

## Architektura

Trzy niezależne źródła danych, każde opcjonalne:

1. **Chmura SmartThings, oficjalnie (PAT/OAuth)**. Z opisu urządzenia (`bleD2D`):
   bateria, z którym telefonem tag był ostatnio połączony, `nearby`, czas
   ostatniego kontaktu. Z tego samego miejsca pochodzi materiał do puli privacy ID.
2. **Lokalnie przez Bluetooth (główna wartość)**. HA Bluetooth / proxy ESPHome
   słucha ramek `0xFD5A`. Każdą ramkę dopasowujemy do konkretnego tagu przez pulę
   privacy ID wygenerowaną z danych z punktu 1. Efekt: obecność per tag, RSSI,
   najbliższe proxy (pokój), stan tagu (przy właścicielu / zgubiony), bateria i
   ruch. Bez odpytywania chmury, działa na rotujących MAC.
3. **GPS z Samsung Find (nieoficjalnie, opcja)**. Proxy SmartApp FME
   (`/trackers/geolocation`) wymaga logowania kontem Samsung, nie PAT. Na dziś
   najlepiej działa gotowa integracja
   [PixelShober/HA-SmartThings-Find](https://github.com/PixelShober/HA-SmartThings-Find).
   Rekomendacja: używać jej równolegle, a własny moduł GPS robić dopiero, gdy
   będzie potrzebny.

Przyciski tagu: obejście przez wirtualny przełącznik w aplikacji SmartThings
(opis w RESEARCH.md).

## Co jest w repo

| Ścieżka | Co |
|---|---|
| `custom_components/smarttag/ble.py` | parser ramek FD5A |
| `custom_components/smarttag/privacy.py` | generowanie puli privacy ID |
| `custom_components/smarttag/cloud.py` | rozpoznawanie tagów i parsowanie `bleD2D` z API SmartThings |
| `tools/st_probe.py` | PoC: co API mówi o Twoich tagach |
| `tests/` | testy pytest |
| `docs/RESEARCH.md` | research ze źródłami |

## Jak uruchomić PoC

1. Wygeneruj PAT na https://account.smartthings.com/tokens (zakresy: urządzenia
   `r:devices:*`, `l:devices`, aplikacje `r:installedapps`, `l:installedapps`).
2. Na maszynie z dostępem do internetu:

```bash
python3 -m venv .venv && .venv/bin/pip install cryptography
export SMARTTHINGS_TOKEN=...      # nie wklejaj tokenu do repo ani do czatu
.venv/bin/python tools/st_probe.py --pool
```

Skrypt wypisze tagi, baterię, ostatnie połączenie i czy da się zbudować pulę
privacy ID. Nie wypisuje tokenu ani kluczy. `--raw dumps/` zapisuje zredagowane
JSON-y (katalog `dumps/` jest w `.gitignore`).

## Roadmapa

- [x] Research i źródła
- [x] Parser FD5A, pula privacy ID, parser `bleD2D`, testy
- [x] PoC na PAT
- [ ] Weryfikacja na prawdziwych tagach: czy PAT dostaje `encryptionKey`, czy ramki w stanie 4 niosą privacy ID z puli
- [ ] Integracja HA: config flow (PAT), koordynator chmury, sensory baterii i ostatniego połączenia
- [ ] Integracja HA: nasłuch Bluetooth, `device_tracker`/obecność per tag, RSSI, najbliższe proxy
- [ ] Rozdzielenie gen 1 / gen 2 w modelu urządzenia
- [ ] (opcja) GPS przez Samsung Find, jeśli PixelShober przestanie wystarczać
- [ ] HACS: `hacs.json`, `manifest.json`, walidacja hassfest/HACS w CI

## Zastrzeżenia

Część wiedzy pochodzi z inżynierii wstecznej (uTag, praca USENIX). Samsung może to
zmienić bez ostrzeżenia. Używaj tylko z własnymi tagami. Sekrety (PAT,
`encryptionKey`) trzymaj wyłącznie w magazynie HA lub zmiennych środowiskowych.

## Licencja

MIT
