# AGENTS.md

## Project
FL Atlas Launcher is a desktop launcher for managing multiple Freelancer installations, MPID profiles, and launch/runtime settings.
It is primarily a PySide6 GUI application with platform-specific behavior for Windows and growing Linux support.

## Main Entry Points
- App start: `python -m app.main`
- Windows convenience launcher: `launch.cmd`
- Packaging spec: `FL-Atlas-Launcher.spec`
- Linux build helper: `scripts/build-linux.sh`

## Setup
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

Alternative local launcher:
```powershell
launch.cmd
```

## Build
- Windows:
```powershell
pip install pyinstaller
pyinstaller FL-Atlas-Launcher.spec
```
- Linux:
```bash
chmod +x scripts/build-linux.sh
./scripts/build-linux.sh
```

## Important Paths
- `app/`: application code
- `app/ui/`: dialogs and UI windows
- `app/services/`: business logic and integration helpers
- `app/models/`: data models
- `scripts/`: build and helper scripts
- `dist-x64/`, `build-x64/`: generated build artifacts

## Working Rules
- No quick fixes. Prefer correct, maintainable solutions that fit the existing architecture.
- Preserve a clean structure and align changes with established software engineering standards.
- Avoid unnecessary or circular code changes where one layer undoes or duplicates another layer's work.
- Prefer small, focused changes over broad refactors.
- Preserve existing UI patterns and naming conventions inside `app/ui/`.
- Keep platform-specific behavior explicit and avoid breaking Windows support while editing Linux-related code.
- Avoid changing packaging files unless the task actually affects startup, assets, or build output.
- Treat config, MPID, and launcher path handling as user-sensitive behavior that should not change accidentally.

## Guardrails
- Do not commit generated build output from `build-x64/` or `dist-x64/` unless explicitly requested.
- Do not rename public-facing settings or config fields without checking migration impact.
- Do not assume Linux and Windows use the same runtime or registry/path behavior.
- Be careful with code that writes config files, registry data, or installation-specific files.
- Do not add workaround logic that hides the real source of a problem when the root cause can be fixed properly.

## Validation
- For Python changes, at minimum run a targeted smoke check that the app starts:
```powershell
python -m app.main
```
- If the task touches packaging, run the relevant PyInstaller or Linux build command.
- If the task touches UI flows, verify the affected dialog/window manually.

## Response Expectations
- Mention any assumptions when behavior is unclear.
- Call out manual checks if a full automated test is not available.
- Prefer describing user-visible impact over listing low-level edits.
