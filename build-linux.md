# Linux Build

## Voraussetzungen

- `python3`
- funktionierende Linux-Desktop-Session
- Internetzugang fuer `pip`

## Build starten

```bash
cd /path/to/FL-Atlas-Launcher
chmod +x scripts/build-linux.sh
./scripts/build-linux.sh
```

## Ergebnis

Der Build landet in:

```text
dist-linux/FL-Atlas-Launcher/
```

Dort liegen:

- `FL-Atlas-Launcher` - das gebaute Binary
- `launch.sh` - einfacher Linux-Starter
- `FL-Atlas-Launcher.desktop` - Desktop-Datei
- `fl_atlas_launcher_icon_512.png` - Icon fuer manuelle Integration

## Hinweise

- Die Build-Umgebung wird in `.venv-linux-build/` erzeugt.
- Laufzeitdaten aus `app/resources/` sowie `HELP.md`, `HELP.en.md` und `README.md` werden in den Build gepackt.
- `PyYAML` wird fuer Lutris-Erkennung als Build-Abhaengigkeit mit installiert.
