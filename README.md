# FL Atlas Launcher

Desktop launcher for managing multiple Freelancer installations.

## Current status

The project currently includes:

- a PySide6 application bootstrap
- local JSON configuration storage
- a main window with installation list
- a settings dialog to add, edit, and remove installations
- a resolution selector scaffold

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```
