# Research: Samsung Galaxy SmartTag w Home Assistant

Stan na 30.10.2026. Każdy wniosek ma źródło na dole.

## 1. Dlaczego wbudowana integracja SmartThings nie daje encji

- Tag jest widoczny w API SmartThings jako urządzenie (`ocfDeviceType: x.com.st.d.tag`, kategoria `BluetoothTracker`) z capability `alarm`, `audioVolume`, `battery`, `geolocation`, `geofence`, `tag.tagButton`, `tag.tagStatus`, `tag.updatedInfo`, `tag.searchingStatus`, `tag.e2eEncryption`, `tag.factoryReset` [S1].
- Ale `GET /v1/devices/{id}/status` zwraca dla wszystkich atrybutów `null`, także `geolocation.latitude/longitude`. Zapytania o komponent geolocation kończą się 403 albo pustką. Dotyczy SmartTag, SmartTag+ i SmartTag2 [S1].
- Dlatego HA najpierw tworzył encje Alarm/Volume/Battery z wartością `unknown` [S2], a od maja 2025 (PR #145066) świadomie tworzy samo urządzenie bez encji [S3]. To nie błąd Twojej konfiguracji, tak ma być.
- Samsung (moderator społeczności): dane tagów są dostępne tylko w SmartApp SmartThings Find [S1].

## 2. Co jednak da się wyczytać oficjalnym API (PAT/OAuth SmartThings)

`GET /v1/devices/{id}` (pełny opis, nie `/status`) zwraca obiekt `bleD2D` [S1][S4]:

| Pole | Co znaczy | Przydatność |
|---|---|---|
| `metadata.battery.level` (`FULL/MEDIUM/LOW/VERY_LOW`) + `updated` | bateria | sensor baterii |
| `metadata.lastKnownConnection` (`connectedDevice.name`, `d2dStatus`, `nearby`, `updated`) | z którym telefonem tag był ostatnio połączony | "przy kim jest tag", heurystyka obecności |
| `metadata.searchingStatus` | czy trwa szukanie | atrybut |
| `encryptionKey`, `metadata.privacyIdSeed`, `privacyIdInitialVector`, `privacyIdPoolSize` | materiał do wygenerowania puli privacy ID | lokalne rozpoznawanie tagu po BLE (sekcja 4) |

Uwaga: dane z 2021 r. (Flobul) i wiki uTag. Czy w 2026 r. PAT nadal dostaje `encryptionKey`, sprawdza `tools/st_probe.py`. To pierwszy krok weryfikacji.

Przyciski: `tag.tagButton` nie trafia do HA, ale w aplikacji SmartThings można przypiąć naciśnięcie/przytrzymanie tagu do wirtualnego przełącznika, a ten HA już widzi [S5][S6].

## 3. Lokalizacja GPS z chmury Samsunga (nieoficjalnie)

- Lokalizacje z sieci Offline Finding zna tylko usługa SmartThings Find / Samsung Find. Publicznego API nie ma.
- **Stary sposób (cookie `JSESSIONID` z smartthingsfind.samsung.com)**: integracja Vedeneb/tomskra (zarchiwizowana) [S7][S8], fork jeena [S9].
- **Nowe Samsung Find (2026)**: `api.samsungfind.com`, token JWT ważny 1 h bez odświeżania. Fork mariosemes uznany za deprecated 31.03.2026, bo wymaga ponownego logowania co godzinę [S10].
- **Działająca droga (2026)**: fork PixelShober (aktywny, ostatni push 28.09.2026) loguje się do konta Samsung jak aplikacja SmartThings (OAuth + PKCE, refresh token) i pyta proxy SmartApp FME: `POST https://api.smartthings.com/installedapps/{FME}/execute` z `uri=/trackers/geolocation`. Daje `device_tracker`, baterię i dzwonienie tagiem [S11]. Format proxy opisuje wiki uTag [S12].
- PAT SmartThings NIE wystarcza do proxy FME: żądanie wymaga `requesterToken` konta Samsung [S10][S11][S12].
- Ograniczenia: API odwrócone inżynieryjnie, używa client ID aplikacji Samsunga, może przestać działać w każdej chwili, szara strefa regulaminu. Tylko do prywatnego użytku.

## 4. Lokalnie przez Bluetooth (HA Bluetooth proxy / ESPHome)

- Tag rozgłasza service data na UUID `0xFD5A`: stan (1 do 3 = bez właściciela, 4 do 6 = połączony), licznik, 8 bajtów privacy ID, bateria, flagi UWB/szyfrowania, ruch, podpis [S13][S14].
- MAC jest losowy, a privacy ID zmienia się co 15 min (co 24 h w stanie overmature), więc proste Bermuda/ESPresense nie rozróżnia tagów i nie ma IRK dla Private BLE Device [S15][S16][S17].
- **Ale** pulę privacy ID da się odtworzyć z `encryptionKey` + `privacyIdSeed` + `privacyIdInitialVector` + `privacyIdPoolSize` (AES-CBC, klucz = SHA-256(key[:16] ‖ 1 ‖ "privacy")[:16]) [S18]. Mając pulę, każdą ramkę FD5A da się przypisać do konkretnego tagu, niezależnie od MAC. To robi uTag na Androidzie.
- Wynik: lokalna, natychmiastowa obecność per tag (jest w domu / w zasięgu którego proxy, RSSI), bez chmury przy każdym odczycie. Nie daje GPS poza domem.
- Do sprawdzenia w praktyce: czy w stanie 4 (połączony z telefonem właściciela) ramka niesie privacy ID z puli i jak często tag nadaje.

## 5. Gen 1 vs gen 2

| | SmartTag (2021) | SmartTag+ (2021) | SmartTag2 (2023) |
|---|---|---|---|
| Radio | BLE | BLE + UWB | BLE + UWB |
| Lokalizacja przez sieć Samsung Find | tak | tak | tak |
| Dane w `/status` API SmartThings | null | null | null |
| `bleD2D` w opisie urządzenia | tak | tak | tak (do weryfikacji) |
| Ramki FD5A | tak | tak | tak (flaga UWB) |
| Precyzja UWB | nie | tylko telefon Galaxy z UWB | tylko telefon Galaxy z UWB |

UWB nie jest dostępne dla HA ani ESP32 (wymaga sesji z telefonem). Z punktu widzenia HA gen 1 i gen 2 działają tak samo.

## Źródła

- [S1] SmartThings Community, "SmartTag on API?": https://community.smartthings.com/t/smarttag-on-api/225995
- [S2] home-assistant/core #139647: https://github.com/home-assistant/core/issues/139647
- [S3] home-assistant/core PR #145066: https://github.com/home-assistant/core/pull/145066
- [S4] uTag wiki, SmartThings Device Info Calls: https://github.com/KieronQuinn/uTag/wiki/SmartThings-Device-Info-Calls
- [S5] HA Community, Smart Tag & Virtual Switch: https://community.home-assistant.io/t/samsung-smartthings-smart-tag-virtual-switch-temp-workaround/357290
- [S6] Frigi.ch, SmartTag 2 and Home Assistant: https://frigi.ch/en/article/2025-smarttags-in-home-assistant/
- [S7] Vedeneb/HA-SmartThings-Find (archiwum): https://github.com/Vedeneb/HA-SmartThings-Find
- [S8] tomskra/HA-SmartThings-Find: https://github.com/tomskra/HA-SmartThings-Find
- [S9] jeena/HA-SmartThings-Find: https://git.jeena.net/jeena/HA-SmartThings-Find
- [S10] mariosemes/HA-SmartThings-Find (deprecated 2026-03-31): https://github.com/mariosemes/HA-SmartThings-Find
- [S11] PixelShober/HA-SmartThings-Find (OAuth fork): https://github.com/PixelShober/HA-SmartThings-Find
- [S12] uTag wiki, Installed Apps Calls: https://github.com/KieronQuinn/uTag/wiki/SmartThings-Installed-Apps-Calls
- [S13] uTag wiki, BLE Service Data: https://github.com/KieronQuinn/uTag/wiki/BLE-Service-Data
- [S14] Yu i in., USENIX Security 2024: https://www.usenix.org/system/files/usenixsecurity24-yu-tingfeng.pdf (arXiv: https://arxiv.org/abs/2210.14702)
- [S15] HA Community, ESPHome BLE & SmartTag: https://community.home-assistant.io/t/esphome-ble-scanner-samsung-smart-tag-has-it-been-done-help/419984
- [S16] HA Community, Private BLE Device & SmartTag: https://community.home-assistant.io/t/private-ble-device-samsung-smarttag/623628
- [S17] Bermuda wiki: https://github.com/agittins/bermuda/wiki/Supported-devices
- [S18] uTag wiki, BLE Privacy ID: https://github.com/KieronQuinn/uTag/wiki/BLE-Privacy-ID
- uTag: https://github.com/KieronQuinn/uTag
- Dokumentacja integracji SmartThings w HA: https://www.home-assistant.io/integrations/smartthings/
