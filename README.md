# FL Atlas Launcher

A desktop launcher for managing multiple Freelancer game installations, player profiles (MPIDs), and screen resolutions — built with PySide6.

## Features

### Installation Management

- Manage multiple Freelancer installations side by side (e.g. vanilla, HD mod, Crossfire, Discovery)
- Each installation stores a custom name, the path to `Freelancer.exe`, and the path to `PerfOptions.ini`
- Double-click an installation to launch it directly
- Running Freelancer processes are detected automatically and highlighted in the list
- Right-click context menu to stop a running instance or open the installation folder in Explorer

### Resolution Management

- Select from 8 preset screen resolutions or use your monitor's native resolution
- The current monitor resolution is detected via a native Windows query (DPI-aware)
- The selected resolution is written to `PerfOptions.ini` automatically
- Your selection is stored persistently and restored on the next launcher start

### MPID Management

Freelancer uses a unique **Multiplayer ID (MPID)** stored in the Windows Registry. The launcher lets you manage multiple MPIDs so you can switch between different player identities:

- **Save** — snapshot the current MPID under a custom name
- **Activate** — restore a saved MPID to the registry
- **Rename** — rename a saved profile
- **Remove** — delete a saved profile from the launcher
- **Delete** — remove the MPID from the Windows Registry
- **Import / Export** — share profiles as files

### MPID Sync

Synchronise your MPID profiles across multiple machines via a shared folder (NAS, VPN, or cloud-synced directory):

- Configure a sync folder in the settings
- On startup the launcher checks reachability and performs one automatic sync
- Background status indicator: **online** · **offline** · **checking…** · **not configured**
- Trigger additional syncs manually with the **Sync** button

### Themes

Six built-in colour themes to choose from:

- Dark Blue (default)
- Red
- Yellow
- Black
- Light
- Green

### Language

The launcher supports **German** and **English**. The language can be changed in the main window and is stored locally.

## Requirements

- Windows 10 / 11 or a modern Linux desktop
- Python 3.8+
- [PySide6](https://pypi.org/project/PySide6/) >= 6.8, < 7.0
- [pefile](https://pypi.org/project/pefile/) >= 2024.8.26

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

On Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Build standalone executable

```powershell
pip install pyinstaller
pyinstaller FL-Atlas-Launcher.spec
```

The output is written to `dist-x64/`.

## Configuration

All settings are stored in a local JSON file at:

```
~/.fl-atlas-launcher/config.json
```

## Linux notes

Each installation can now be configured with a dedicated launch/runtime setup:

- `Launch Method`: `Wine / Proton`, `Bottles`, `Steam`, `Lutris`, or `Automatic`
- `Wine / Proton Prefix`: host path to the prefix, for example `~/.steam/steam/steamapps/compatdata/<id>/pfx`
- `Runner Target`:
  - Bottles: bottle name
  - Steam: App ID or shortcut ID
  - Lutris: game slug or numeric game ID
- `Launch Arguments`: optional extra arguments passed to the launcher command

Path handling on Linux accepts both native Linux paths and common Wine-style drive paths such as `Z:\home\user\...` or `C:\...` inside the configured prefix.

MPID management on Linux works against the selected installation's Wine/Proton prefix (`user.reg`) instead of the host Windows registry. If you want MPID switching to work, set the correct prefix for that installation.

## License

This project is not open-source. All rights reserved.
