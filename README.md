# FL Atlas Launcher

Desktop launcher for managing multiple Freelancer installations.

## Current status

The project currently includes:

- a PySide6 application bootstrap
- local JSON configuration storage
- a main window with installation list
- a settings dialog to add, edit, and remove installations
- a resolution selector scaffold
- running-process detection with highlighted installation icons
- a context menu for stopping a running Freelancer.exe
- a cheater mode sidebar with BINI conversion, Reveal Everything, and ship-handling tools

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```
