# FL Atlas Launcher Help

## Overview

FL Atlas Launcher manages multiple Freelancer installations, applies the selected resolution before launch, and provides multiplayer ID (MPID) management including import, export, and optional sync.

The official online help is available here:

https://github.com/flathack/FL-Atlas-Launcher/wiki

## Main Window

In the main window you can:

- select a saved multiplayer ID
- select a resolution
- start a Freelancer installation by double-clicking it or by using `Launch`
- manage installations and MPIDs from the top bar

## Manage Installations

Under `Manage Installations` you can store multiple Freelancer versions.

Each entry stores:

- a custom display name
- the path to `Freelancer.exe`
- the path to `PerfOptions.ini`

Before launch, the launcher writes the selected resolution into the corresponding `PerfOptions.ini`.

## Manage Multiplayer IDs

Under `Manage MPIDs` you can back up and reactivate Freelancer multiplayer IDs.

Functions:

- `Save Current ID`: reads the current Freelancer MPID from the registry and stores it as a profile
- `Activate Selected ID`: writes the selected profile back to the registry
- `Remove Current ID`: removes the known current MPID from the registry so Freelancer can generate a new one later
- `Import`: loads MPID profiles from a JSON file
- `Export`: writes MPID profiles to a JSON file
- `Sync`: synchronizes local MPID profiles with the configured sync folder
- `Rename`: renames the selected profile
- `Delete`: removes the selected profile from the launcher

Notes:

- The profile currently active in the registry is shown in bold in the list.
- Already saved IDs cannot be stored again as a new profile.
- The registry fields stored in a profile are shown read-only on the right side of the dialog.

## Sync

Sync is intended as an additional backup and synchronization option, for example through a NAS or a folder reachable through VPN.

Important:

- The actual launcher configuration stays stored locally on the PC.
- The sync folder is only used for MPID profiles.
- On startup, the launcher checks whether the sync folder is reachable.
- If the folder is reachable, one automatic sync is performed.
- After that, only the status check continues in the background.
- Any additional sync must be triggered manually with the `Sync` button.

Status in the main window:

- `online`: sync folder is reachable
- `offline`: sync folder is currently not reachable
- `checking...`: reachability is currently being checked
- `not configured`: no sync folder has been configured yet

## Resolution

The selected resolution is stored persistently in the launcher. On the next launcher start, the same selection is restored.

The current monitor resolution is detected using a native Windows query so DPI scaling does not distort the value.

## Language

The launcher currently supports:

- German
- English

The language can be changed in the main window and is stored locally.

## Troubleshooting

### Sync is offline

Check:

- whether the configured folder still exists
- whether your NAS or VPN connection is reachable
- whether you have permissions to access the folder

### Freelancer does not start

Check:

- whether the path to `Freelancer.exe` is still correct
- whether the path to `PerfOptions.ini` is still correct
- whether the selected resolution is supported

### No MPID found

If no MPID is found, there are currently no matching values in the Freelancer registry. In that case, you need to start Freelancer in a state where it recreates the MPID.
