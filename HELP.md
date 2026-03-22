# FL Atlas Launcher Hilfe

## Überblick

Der FL Atlas Launcher verwaltet mehrere Freelancer-Installationen, setzt die gewünschte Auflösung vor dem Start und bietet eine Verwaltung für Multiplayer-IDs (MPIDs) inklusive Import, Export und optionalem Sync.

Die offizielle Online-Hilfe ist hier erreichbar:

https://github.com/flathack/FL-Atlas-Launcher/wiki

## Hauptfenster

Im Hauptfenster kannst du:

- eine gespeicherte Multiplayer-ID auswählen
- eine Auflösung auswählen
- eine Freelancer-Installation per Doppelklick oder über `Starten` starten
- Installationen und MPIDs über die obere Leiste verwalten

## Installationen verwalten

Unter `Installationen verwalten` kannst du mehrere Freelancer-Versionen hinterlegen.

Pro Eintrag werden gespeichert:

- ein frei wählbarer Name
- der Pfad zur `Freelancer.exe`
- der Pfad zur `PerfOptions.ini`

Vor dem Start schreibt der Launcher die ausgewählte Auflösung in die jeweilige `PerfOptions.ini`.

## Multiplayer-IDs verwalten

Unter `MPIDs verwalten` kannst du Freelancer-Multiplayer-IDs sichern und wieder aktivieren.

Funktionen:

- `Aktuelle ID speichern`: liest die aktuelle Freelancer-MPID aus der Registry und speichert sie als Profil
- `Ausgewählte ID aktivieren`: schreibt das gewählte Profil zurück in die Registry
- `Aktuelle ID entfernen`: entfernt die bekannte aktuelle MPID aus der Registry, damit Freelancer später eine neue erzeugen kann
- `Import`: lädt MPID-Profile aus einer JSON-Datei
- `Export`: schreibt MPID-Profile in eine JSON-Datei
- `Sync`: gleicht die lokalen MPID-Profile mit dem konfigurierten Sync-Ordner ab
- `Umbenennen`: benennt das gewählte Profil um
- `Löschen`: entfernt das gewählte Profil aus dem Launcher

Hinweise:

- Das aktuell in der Registry aktive Profil wird in der Liste fett dargestellt.
- Bereits gespeicherte IDs können nicht noch einmal als neues Profil gespeichert werden.
- Rechts im Dialog werden die im Profil gespeicherten Registry-Felder nur lesbar angezeigt.

## Sync

Der Sync ist für zusätzliche Sicherung und Abgleich gedacht, zum Beispiel über ein NAS oder einen VPN-erreichbaren Ordner.

Wichtig:

- Die eigentliche Launcher-Konfiguration bleibt lokal auf dem PC gespeichert.
- Der Sync-Ordner wird nur für MPID-Profile verwendet.
- Beim Start prüft der Launcher, ob der Sync-Ordner erreichbar ist.
- Ist der Ordner erreichbar, wird einmal automatisch abgeglichen.
- Danach erfolgt nur noch eine Statusprüfung im Hintergrund.
- Ein erneuter manueller Abgleich erfolgt über den `Sync`-Button.

Status im Hauptfenster:

- `online`: Sync-Ordner ist erreichbar
- `offline`: Sync-Ordner ist aktuell nicht erreichbar
- `prüft...`: Erreichbarkeit wird gerade geprüft
- `nicht konfiguriert`: Es wurde noch kein Sync-Ordner gesetzt

## Auflösung

Die gewählte Auflösung wird persistent im Launcher gespeichert. Beim nächsten Start des Launchers wird diese Auswahl wieder geladen.

Die Erkennung der aktuellen Monitorauflösung verwendet eine native Windows-Abfrage, damit DPI-Skalierung die Werte nicht verfälscht.

## Sprache

Der Launcher unterstützt aktuell:

- Deutsch
- Englisch

Die Sprache kann oben im Hauptfenster umgeschaltet werden und wird lokal gespeichert.

## Fehlerbehebung

### Sync ist offline

Prüfe:

- ob der konfigurierte Ordner noch existiert
- ob NAS oder VPN erreichbar sind
- ob du Zugriffsrechte auf den Ordner hast

### Freelancer startet nicht

Prüfe:

- ob der Pfad zur `Freelancer.exe` noch stimmt
- ob der Pfad zur `PerfOptions.ini` noch stimmt
- ob die gewählte Auflösung unterstützt wird

### Keine MPID gefunden

Wenn keine MPID gefunden wird, existieren in der Freelancer-Registry aktuell keine passenden Werte. In diesem Fall musst du zuerst Freelancer in einem Zustand starten, in dem die MPID wieder angelegt wird.
