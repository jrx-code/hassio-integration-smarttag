# SmartTag dla Home Assistant

Własna integracja dla Samsung Galaxy SmartTag (gen 1, SmartTag+ i SmartTag2).
Cel: z tagów, które we wbudowanej integracji SmartThings nie mają żadnych encji,
zrobić w HA obecność, baterię i (opcjonalnie) położenie GPS.

> Status: wersja 0.1.0, eksperymentalna. Nie sprawdzona jeszcze na prawdziwych
> tagach (patrz Roadmapa).

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

## Instalacja (HACS, repozytorium własne)

1. HACS > Integracje > menu > Repozytoria niestandardowe > `https://github.com/jrx-code/hassio-integration-smarttag`, kategoria Integracja.
2. Zainstaluj "Samsung SmartTag", zrestartuj HA.
3. Ustawienia > Urządzenia i usługi > Dodaj integrację > Samsung SmartTag.
4. Źródło tokenu:
   - `smartthings` (zalecane): integracja pożycza aktualny token OAuth z wbudowanej integracji SmartThings. Tylko go czyta, nie odświeża.
   - `pat`: Personal Access Token. Uwaga: PAT utworzone po 30.12.2024 żyją tylko 24 h. Wystarczy to do pobrania puli privacy ID (zapisywana lokalnie), potem BLE działa bez chmury, a sensory z chmury przestają się aktualizować.

Potrzebny jest Bluetooth w HA: adapter albo proxy ESPHome (`bluetooth_proxy:`). Najlepiej kilka proxy w różnych pokojach.

### Encje na każdy tag

| Encja | Źródło | Opis |
|---|---|---|
| `binary_sensor.*_w_zasiegu` | BLE | widziany w ostatnich N s (domyślnie 300, zmiana w Opcjach); atrybuty: proxy, RSSI, stan, ruch |
| `sensor.*_bateria` | BLE, inaczej chmura | 100/50/15/5 % (Samsung podaje 4 poziomy) |
| `sensor.*_sygnal_ble` | BLE | RSSI i proxy, które złapało ramkę |
| `sensor.*_stan_tagu` | BLE | przy właścicielu / bez właściciela / połączony z obcym |
| `sensor.*_ostatnio_polaczony_z` | chmura | nazwa telefonu, `nearby`, czas |

## Co jest w repo

| Ścieżka | Co |
|---|---|
| `custom_components/smarttag/ble.py` | parser ramek FD5A |
| `custom_components/smarttag/privacy.py` | generowanie puli privacy ID |
| `custom_components/smarttag/cloud.py` | rozpoznawanie tagów i parsowanie `bleD2D` z API SmartThings |
| `custom_components/smarttag/coordinator.py`, `api.py` | koordynator: chmura co 30 min, nasłuch BLE, pamięć puli |
| `custom_components/smarttag/config_flow.py` | konfiguracja w UI, reauth, opcje |
| `tools/st_probe.py` | PoC: co API mówi o Twoich tagach |
| `tests/` | testy pytest |
| `docs/RESEARCH.md` | research ze źródłami |

## Jak uruchomić PoC

1. Wygeneruj PAT (ważny 24 h) na https://account.smartthings.com/tokens (zakresy: urządzenia
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
- [x] Integracja HA: config flow (token z integracji SmartThings albo PAT), koordynator chmury, sensory
- [x] Integracja HA: nasłuch Bluetooth, obecność per tag, RSSI, proxy
- [ ] `device_tracker` (home/not_home) i ewentualnie integracja z Bermuda (pokój)
- [ ] Rozdzielenie gen 1 / gen 2 w modelu urządzenia
- [ ] (opcja) GPS przez Samsung Find, jeśli PixelShober przestanie wystarczać
- [x] HACS: `hacs.json`, `manifest.json`, walidacja hassfest/HACS w CI
- [ ] Brands (ikona) i zgłoszenie do HACS default

## Zastrzeżenia

Część wiedzy pochodzi z inżynierii wstecznej (uTag, praca USENIX). Samsung może to
zmienić bez ostrzeżenia. Używaj tylko z własnymi tagami. Sekrety (PAT,
`encryptionKey`) trzymaj wyłącznie w magazynie HA lub zmiennych środowiskowych.

## Licencja

MIT
