# FL Atlas Launcher

Kleiner Desktop Launcher fuer Freelancer.

Gedacht fuer Leute, die mehrere FL Installationen, Mods, MPIDs und Settings nicht mehr per Hand jonglieren wollen.

## Was kann das Ding?

- mehrere Freelancer Installationen verwalten
- MPID Profile speichern und wechseln
- Aufloesung setzen
- Freelancer starten
- laufende Instanzen erkennen
- Trade Routes anschauen
- Ship Infos und Handling ansehen
- Universe Viewer nutzen
- Windows first, Linux Support ist aber drin und waechst weiter

## Starten

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

Oder auf Windows einfach:

```powershell
launch.cmd
```

## Build

Windows:

```powershell
pip install pyinstaller
pyinstaller FL-Atlas-Launcher.spec
```

Linux:

```bash
chmod +x scripts/build-linux.sh
./scripts/build-linux.sh
```

## Config

Die Settings liegen lokal als JSON.
MPIDs, Pfade und Installationen sind user-sensibel, also nicht blind wegwerfen.

## Requirements

- Python
- PySide6
- pefile
- Freelancer Installation
- bisschen Geduld, wenn Windows wieder Windows macht

## Status

Work in progress.
Wenn was komisch aussieht: wahrscheinlich UI Baustelle oder irgendein Path-Mapping Ding.

## License

Private project. All rights reserved.
