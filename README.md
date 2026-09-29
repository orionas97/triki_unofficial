# Triki (Żabka) — integracja z Home Assistant

**English TL;DR:** Unofficial Home Assistant custom integration for the "Triki" BLE bottle-cap controller given away by the Polish Żabka convenience store chain (Żappka app gamification gadget). Connects over Bluetooth (local adapter or an ESPHome Bluetooth proxy), exposes battery/firmware/RSSI sensors, raw accelerometer (g) and gyroscope (°/s) sensors, a button sensor, an LED switch, and derived position/rotation binary sensors. Not affiliated with Żabka Polska or the device's manufacturer. See below (in Polish) for full installation and usage instructions.

---

## ⚠️ Status i zastrzeżenia

- To jest integracja **nieoficjalna**, stworzona przez odwrócenie protokołu BLE przez społeczność. Nie jest powiązana z Żabka Polska, HopX ani żadnym oficjalnym producentem Triki.
- Protokół BLE nie jest publicznie udokumentowany przez producenta — wszystko poniżej opiera się na projektach reverse-engineeringowych wymienionych w sekcji [Podziękowania](#podziękowania-i-źródła) oraz na realnych danych zebranych z fizycznego urządzenia.
- Kierunek obrotu (`obrot_prawo`/`obrot_lewo`) i przypisanie „lewo"/„prawo" dla pozycji bocznej **nie są niezależnie zweryfikowane fizycznie** — zależą od tego, jak płytka BLE jest zamontowana wewnątrz konkretnego egzemplarza kapsla. Mogą wymagać odwrócenia na Twoim urządzeniu (patrz [Rozwiązywanie problemów](#rozwiązywanie-problemów)).
- Triki komunikuje się przez Bluetooth Low Energy i **przyjmuje tylko jedno aktywne połączenie na raz**. Jeśli kapsel jest połączony z aplikacją Żappka na telefonie, Home Assistant się z nim nie połączy.

## Co to jest Triki

Triki to kontroler w kształcie kapsla od piwa/napoju, rozdawany w ramach promocji aplikacji Żappka (Żabka Polska). Zawiera moduł BLE, 6-osiowy czujnik IMU (akcelerometr + żyroskop), przycisk i diodę LED, i służy jako kontroler ruchowy do minigier w aplikacji Żappka (rzucanie, obracanie, przechylanie kapsla).

## Funkcje / Encje

| Encja | Typ | Opis | Domyślnie włączona |
|---|---|---|---|
| Bateria | `sensor` | Poziom baterii (%) | ✅ |
| Wersja firmware | `sensor` | Wersja oprogramowania urządzenia | ❌ (diagnostyczna) |
| Siła sygnału (RSSI) | `sensor` | Siła sygnału BLE (dBm) | ❌ (diagnostyczna) |
| Akcelerometr X/Y/Z | `sensor` | Przyspieszenie w osiach X/Y/Z (g) | ❌ |
| Żyroskop X/Y/Z | `sensor` | Prędkość kątowa w osiach X/Y/Z (°/s) | ❌ |
| Przycisk | `binary_sensor` | Czy fizyczny przycisk jest wciśnięty | ✅ |
| Połączenie | `binary_sensor` | Czy HA ma aktywne połączenie BLE z kapslem | ✅ (diagnostyczna) |
| Pozycja: góra | `binary_sensor` | Kapsel leży płasko, logo/przyciskiem do góry | ✅ |
| Pozycja: dół | `binary_sensor` | Kapsel leży płasko, logo/przyciskiem w dół | ✅ |
| Pozycja: poziom | `binary_sensor` | Kapsel leży płasko (góra LUB dół) | ✅ |
| Pozycja: pion | `binary_sensor` | Kapsel stoi na swojej krawędzi (nie leży płasko) | ✅ |
| Pozycja: bok (lewo/prawo) | `binary_sensor` | Kapsel oparty na boku — etykieta lewo/prawo niezweryfikowana | ❌ |
| Obrót w prawo/lewo | `binary_sensor` | Kapsel aktualnie się obraca — kierunek niezweryfikowany | ✅ |
| LED | `switch` | Włącza/wyłącza wbudowaną zieloną diodę | ✅ |

Encje pozycji są aktywne **tylko gdy kapsel realnie leży spokojnie** (~1g łącznie na akcelerometrze) — podczas aktywnego ruchu żadna z nich nie jest włączona, to celowe zachowanie (unika fałszywych odczytów podczas rzucania/kręcenia kapslem).

## Wymagania

- Home Assistant Core z działającą integracją Bluetooth: wbudowany adapter Bluetooth hosta, dongle USB Bluetooth, **lub** [ESPHome Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy/) w trybie aktywnym.
- Jeśli używasz ESPHome Bluetooth Proxy, w konfiguracji ESP musi być:
  ```yaml
  esp32_ble_tracker:
    scan_parameters:
      active: true
  bluetooth_proxy:
    active: true
  ```
- Triki musi być **odłączone od aplikacji Żappka** (patrz sekcja niżej).

## Instalacja

### Metoda 1: ręcznie (zalecana)

1. Pobierz zawartość repozytorium (Code → Download ZIP) albo sklonuj je:
   ```bash
   git clone https://github.com/orionas97/triki_unofficial.git
   ```
2. Skopiuj folder `custom_components/triki` do folderu konfiguracyjnego Home Assistant, tak żeby istniała ścieżka:
   ```
   /config/custom_components/triki/manifest.json
   ```
3. Zrestartuj Home Assistant: **Ustawienia → System → Uruchom ponownie**.

### Metoda 2: przez HACS (custom repository)

1. HACS → menu (⋮) w prawym górnym rogu → **Custom repositories**.
2. Wklej adres: `https://github.com/orionas97/triki_unofficial`, kategoria: **Integration**.
3. Znajdź „Triki (Żabka)" na liście, zainstaluj.
4. Zrestartuj Home Assistant.

> Uwaga: nazwa repozytorium to `triki_unofficial`, ale wewnętrzny identyfikator integracji (domena) to `triki` — to celowe i nie ma na nic wpływu.

## Dodawanie kontrolera do Home Assistant

1. **Odłącz Triki od telefonu**: wymuś zatrzymanie aplikacji Żappka (Android: Ustawienia → Aplikacje → Żappka → Wymuś zatrzymanie; iOS: zamknij aplikację przesunięciem) i najlepiej wyłącz Bluetooth w telefonie, żeby się nie połączyło ponownie automatycznie.
2. Obudź Triki (naciśnij przycisk / poruszaj kapslem).
3. W Home Assistant: **Ustawienia → Urządzenia i usługi**.
   - Jeśli Triki jest w zasięgu, powinno pojawić się samo jako nowo wykryte urządzenie — kliknij **Skonfiguruj**.
   - Jeśli nie, kliknij **+ Dodaj integrację**, wyszukaj „Triki (Żabka)" i wybierz urządzenie z listy.
4. Po dodaniu Home Assistant automatycznie doinstaluje wymagane biblioteki Pythona (`bleak`, `bleak-retry-connector`).

## Konfiguracja / opcje

Na karcie integracji kliknij **Konfiguruj**, żeby zmienić częstotliwość próbkowania IMU (26 / 52 / 104 / 208 / 416 Hz). Wyższa wartość = szybsza reakcja, ale więcej ruchu Bluetooth i szybsze zużycie baterii kapsla.

## Przykładowa automatyzacja

```yaml
automation:
  - alias: "Triki: włącz światło gdy obrócone w prawo"
    trigger:
      - platform: state
        entity_id: binary_sensor.triki_xxxxxx_obrot_w_prawo
        to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.salon
```

(Podmień `triki_xxxxxx` na rzeczywiste ID Twojego urządzenia — sprawdzisz je w **Narzędzia deweloperskie → Stany**.)

## Wykluczenie osi z rejestratora historii

Surowe osie akcelerometru/żyroskopu (jeśli je włączysz) potrafią zmieniać się nawet setki razy na sekundę. W `configuration.yaml`:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.triki_*_akcelerometr_*
      - sensor.triki_*_zyroskop_*
```

## Rozwiązywanie problemów

| Objaw | Prawdopodobna przyczyna | Rozwiązanie |
|---|---|---|
| Integracja nie widzi urządzenia w ogóle | Kapsel połączony z telefonem/Żappką, albo poza zasięgiem | Wymuś zatrzymanie Żappki, wyłącz BT w telefonie, zbliż ESP/adapter |
| `connection failed (TimeoutError())` w logach | Triki nie przyjmuje połączenia (najczęściej wciąż trzymane przez telefon) lub proxy ESP w trybie pasywnym | Sprawdź `active: true` w konfiguracji ESP; sprawdź telefon |
| Encje widoczne, ale „niedostępne" | Połączenie BLE jeszcze się nie udało (działa w tle) | Sprawdź logi `custom_components.triki` na poziomie INFO |
| `BleakGATTProtocolError: Unlikely Error` przy przełączaniu LED | Zaobserwowany, przejściowy błąd przy połączeniu przez proxy ESP | Integracja automatycznie ponawia próbę 3 razy; jeśli nadal nie działa, zgłoś issue z logami |
| „Obrót w prawo" włącza się przy obrocie w lewo (i odwrotnie) | Orientacja płytki BLE wewnątrz kapsla różni się między egzemplarzami | Zgłoś się przez issue — zamiana zajmuje jedną linijkę w `coordinator.py` |
| „Pozycja: bok (lewo)" włącza się po niewłaściwej stronie | j.w. | j.w. |

Żeby zebrać szczegółowe logi do zgłoszenia błędu, dodaj w `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.triki: debug
```

## Jak to działa (dla ciekawych)

- Triki reklamuje się przez BLE pod nazwą zawierającą `Triki`/`TRIKI` i udostępnia usługę Nordic UART Service (`6e400001-...`) do komunikacji oraz standardowe charakterystyki `Battery Level` i `Firmware Revision`.
- Po połączeniu integracja wysyła komendę startu strumienia IMU i nasłuchuje powiadomień: 16-bajtowa ramka zawiera żyroskop (X/Y/Z), akcelerometr (X/Y/Z) i flagę przycisku.
- Skala: akcelerometr ±16 g (2048 LSB/g), żyroskop ±2000°/s (14.286 LSB/(°/s)) — czujnik LSM6DSL.
- Pozycja (góra/dół/pion/poziom) jest wyliczana lokalnie w integracji na podstawie tego, która oś akcelerometru dominuje, gdy urządzenie leży spokojnie — to nie jest coś, co samo urządzenie raportuje.

## Podziękowania i źródła

Ta integracja nie powstałaby bez wcześniejszej pracy reverse-engineeringowej społeczności:

- [Wojtekb30/unofficial-triki-api-py](https://github.com/Wojtekb30/unofficial-triki-api-py) — biblioteka Python (Bleak), pierwszy opis komend BLE.
- [woofter-wolf/triki-library-python](https://github.com/woofter-wolf/triki-library-python) — niezależna biblioteka Python, m.in. odczyt baterii i flagi przycisku.
- [Flopsstuff/triki](https://github.com/Flopsstuff/triki) — szczegółowa dokumentacja protokołu BLE i skali czujników IMU.

## Licencja

Ten projekt jest objęty licencją MIT (patrz plik [LICENSE](LICENSE)).

## Zgłaszanie błędów

Użyj zakładki [Issues](https://github.com/orionas97/triki_unofficial/issues) tego repozytorium. Dołącz logi z `custom_components.triki` (patrz sekcja [Rozwiązywanie problemów](#rozwiązywanie-problemów)) — bez nich trudno cokolwiek zdiagnozować.
