# FL Atlas Launcher

## Ziel

Eine kleine, moderne Windows-Launcher-App fuer `Freelancer`, die mehrere Installationen verwalten, die Aufloesung komfortabel setzen und Spiele direkt starten kann. Die App ist Teil der `FL Atlas Suite` und soll spaeter weitere Tools verlinken, starten oder herunterladen koennen.

## Produktvision

Der Launcher soll die zentrale Startoberflaeche fuer Freelancer und zusaetzliche FL-Atlas-Tools werden:

- mehrere Freelancer-Installationen verwalten
- pro Installation einen frei waehllbaren Namen und das EXE-Icon anzeigen
- vor dem Start die gewuenschte Aufloesung in `PerfOptions.ini` setzen
- moeglichst einfach und optisch ansprechend bedienbar sein
- updatefaehig, mehrsprachig und themenfaehig sein

## Empfohlener Tech-Stack

- Sprache: `Python 3.12+`
- GUI: `PySide6`
- Styling/Theming: `Qt Stylesheets` plus optional `qdarktheme`
- Lokale Konfiguration: `JSON`
- Packaging: `PyInstaller`
- HTTP/Downloads: `httpx`
- GitHub Release Check: GitHub Releases API
- Internationalisierung: Qt `QTranslator` oder eigenes i18n-Layer auf JSON-Basis
- Logging: Python `logging`

## Warum PySide6

- moderne Desktop-GUI mit guter Windows-Integration
- sehr flexibel fuer ein schickes UI
- gute Unterstuetzung fuer Icons, Dialoge, Themes und Mehrsprachigkeit
- langfristig besser skalierbar als minimalistische GUI-Frameworks

## Kernfunktionen

### 1. Launcher Startseite

- kleines Hauptfenster
- Liste oder Grid mit allen bekannten Freelancer-Installationen
- pro Eintrag:
  - benutzerdefinierter Name
  - Icon aus `Freelancer.exe`
  - Start-Button
  - optional Shortcut zu Bearbeiten

### 2. Installationen verwalten

- Settings-Menue oder separater Verwalten-Dialog
- Installation hinzufuegen
- Pfad zu `Freelancer.exe` angeben
- optional alternativen Pfad zu `PerfOptions.ini` angeben
- Anzeigename frei vergeben
- Installation bearbeiten und loeschen

### 3. Aufloesung setzen

- globale Auswahl im Hauptfenster unterhalb der Launcher-Eintraege
- Standardwert = aktuelle Monitor-Aufloesung
- vor dem Start:
  - `PerfOptions.ini` laden
  - `[Display] size=` anpassen
  - vorhandene Werte fuer `color_bpp` und `depth_bpp` beibehalten oder sinnvoll setzen
- Fallback-Pfad standardmaessig:
  - `%USERPROFILE%\Documents\My Games\Freelancer\PerfOptions.ini`
- pro Installation optional ueberschreibbar

### 4. FL Atlas Suite Bereich

- kleine Tool-Kacheln oder Icon-Buttons fuer weitere Suite-Apps
- Beispiele:
  - Savegame Editor
  - FL Atlas Visual Editor
- Verhalten je Tool:
  - lokal starten, wenn installiert
  - ansonsten Download-Seite oder Release oeffnen

### 5. Updates

- App prueft beim Start oder manuell auf neue GitHub Releases
- Benutzer bekommt Hinweis bei neuer Version
- spaeter optional:
  - Installer herunterladen
  - Update-Prozess anstossen

### 6. UX Features

- Hell- und Dunkel-Theme
- Deutsch und Englisch
- saubere Fehlerdialoge
- Statusmeldungen fuer Speichern, Starten und Updatecheck

## MVP

Die erste nuetzliche Version soll nur das enthalten, was fuer den Kernworkflow notwendig ist:

- modernes Hauptfenster mit Installationsliste
- Installationen hinzufuegen, bearbeiten, loeschen
- Name, EXE-Pfad, optional `PerfOptions.ini`-Pfad speichern
- EXE-Icon lesen und anzeigen
- aktuelle Monitor-Aufloesung erkennen
- Aufloesung aus Dropdown auswaehlbar machen
- `PerfOptions.ini` vor dem Start aktualisieren
- Freelancer starten
- Konfiguration lokal speichern

## Version 1.1

- Hell-/Dunkel-Theme
- Deutsch/Englisch
- FL-Atlas-Suite-Bereich
- manueller GitHub-Updatecheck

## Version 1.2

- automatischer Update-Hinweis beim Start
- Download neuer Version
- robusteres Fehlerhandling
- bessere Validierung fuer Pfade und INI-Dateien

## Version 1.3+

- echter Auto-Updater
- mehrere Aufloesungsprofile
- pro Installation individuelle Startoptionen
- Import/Export der Launcher-Konfiguration
- Erkennung weiterer FL-Atlas-Tools

## Datenmodell

Vorgeschlagene lokale Konfigurationsdatei, z. B. `config.json`:

```json
{
  "theme": "system",
  "language": "de",
  "selected_resolution": "1920x1080",
  "installations": [
    {
      "id": "uuid",
      "name": "Freelancer HD",
      "exe_path": "C:\\Program Files\\Freelancer\\EXE\\Freelancer.exe",
      "perf_options_path": "C:\\Users\\Steve\\Documents\\My Games\\Freelancer\\PerfOptions.ini"
    }
  ],
  "suite_apps": [
    {
      "id": "savegame-editor",
      "name": "Savegame Editor",
      "installed_path": null,
      "download_url": "https://github.com/..."
    }
  ]
}
```

## Projektstruktur

Vorschlag fuer den initialen Aufbau:

```text
FL-Atlas-Launcher/
  app/
    main.py
    bootstrap.py
    ui/
      main_window.py
      settings_dialog.py
      widgets/
    services/
      config_service.py
      launcher_service.py
      resolution_service.py
      ini_service.py
      icon_service.py
      update_service.py
      suite_service.py
    models/
      installation.py
      app_config.py
    resources/
      icons/
      translations/
      styles/
  tests/
  requirements.txt
  README.md
  todo.md
```

## Technische Leitlinien

- klare Trennung zwischen UI, Services und Modellen
- keine Business-Logik direkt in Widgets
- Dateipfade und Konfiguration zentral kapseln
- alle Dateioperationen defensiv behandeln
- Logging fuer Fehler und wichtige Aktionen
- Update- und Downloadlogik kapseln, nicht in UI mischen

## Kritische Punkte / Risiken

### 1. Auto-Updater

Ein vollautomatischer Self-Updater ist unter Windows aufwendiger als ein normaler Updatecheck. Fuer die erste Version sollte nur ein sicherer Release-Check plus Download vorgesehen werden.

### 2. Icon aus EXE lesen

Das Auslesen von EXE-Icons kann je nach Implementierung etwas spezieller sein. Dafuer sollte frueh eine robuste Loesung getestet werden.

### 3. PerfOptions.ini Robustheit

Die Datei kann fehlen, ein anderes Encoding haben oder anders formatiert sein. Das Parsen und Schreiben muss fehlertolerant sein.

### 4. Mehrmonitor-Setup

Die "aktuelle Monitor-Aufloesung" muss sauber definiert werden. Praktisch ist meist: primaerer Bildschirm oder Bildschirm, auf dem das Fenster liegt.

## Offene Entscheidungen

- Soll die Aufloesung global fuer alle Installationen gelten oder pro Installation gespeichert werden?
- Soll der Launcher nur DE/EN unterstuetzen oder spaeter beliebig erweiterbar sein?
- Sollen Suite-Tools nur verlinkt werden oder auch zentral installiert/aktualisiert werden?
- Reicht fuer Updates ein Installer-Download oder ist echter In-App-Update zwingend?

## Umsetzung in Phasen

### Phase 1: Grundgeruest

- Projektstruktur anlegen
- PySide6 App bootstrap
- Hauptfenster mit Platzhalterdaten
- Konfigurationsdatei laden/speichern

### Phase 2: Installationsverwaltung

- Dialog fuer Hinzufuegen/Bearbeiten
- Pfadvalidierung fuer `Freelancer.exe`
- Liste gespeicherter Installationen anzeigen
- Icons aus EXE laden

### Phase 3: Startlogik

- Monitor-Aufloesung erkennen
- Aufloesungen im UI anbieten
- `PerfOptions.ini` lesen und schreiben
- Freelancer starten

### Phase 4: Produktreife

- Theme-Umschaltung
- Mehrsprachigkeit
- Fehlerdialoge und Logging
- Tests fuer Services

### Phase 5: Ecosystem

- Suite-Tool-Kacheln
- GitHub Release Check
- Download-/Updatefluss

## Definition of Done fuer MVP

- Benutzer kann mindestens eine Installation anlegen
- Launcher zeigt Name und Icon an
- Benutzer kann eine Aufloesung auswaehlen
- Vor dem Start wird `PerfOptions.ini` korrekt aktualisiert
- Freelancer startet erfolgreich
- Konfiguration bleibt nach Neustart erhalten
- App wirkt visuell ordentlich und stabil

## Naechster Implementierungsschritt

Zuerst das technische Grundgeruest bauen:

- `PySide6` Projekt anlegen
- Hauptfenster mit Installationsliste
- lokale `config.json`
- Settings-Dialog fuer Installationen

Danach direkt die Aufloesungs- und Startlogik umsetzen, weil das der wichtigste Nutzwert des Launchers ist.
