# Road Lab Blender Extension — updater foundation

This directory is an integration scaffold, **not** the complete Road Lab add-on. Do not install over an existing Road Lab installation until its real code and identifiers are migrated.

## What gets downloaded?
Blender installs versioned extension ZIP files from a configured remote extension repository (its index.json feed). GitHub holds source code; a GitHub branch alone is not a Blender update server.

## Release channels
- Stable: `/stable/index.json` and vetted release ZIPs.
- Beta: `/beta/index.json` and prerelease ZIPs.
Publish to separate hosting paths, and test channel isolation before attempting simultaneous installation.

## Local build
Requires Blender 4.2+ on PATH and a POSIX shell:

```sh
bash road-lab-updater/tools/build_repository.sh
```

The script validates the extension, builds a ZIP, and generates `road-lab-updater/dist/stable/index.json`. This does **not** publish an update service.

## Setup
1. Replace the placeholder `extension/__init__.py` with the actual Road Lab source while preserving its registration, add-on preferences and data migration support.
2. Review the manifest's id, version, maintainer, and licensing to match the actual add-on.
3. Validate in Blender, test with old .blend projects, and build ZIPs.
4. Publish ZIPs and generated index.json to HTTPS release hosting. If private, ensure Blender supports the chosen authentication approach; never embed long-lived tokens in distributed code.
5. In Blender Preferences > Get Extensions > Repositories add the relevant repository URL; use Blender's extension manager to check for and install updates.

Future releases become available inside Blender **only when** a higher compatible version is correctly packaged and published to the configured feed. Updates are not guaranteed merely from Git commits. Backups and a manual rollback archive are recommended.

## Safety
Do not overwrite or delete saved Blender project data. Test migrations and restart behavior. Keep stable releases separate from prereleases. Native Blender checks/installs are generally user-controlled rather than silent force-updates.
