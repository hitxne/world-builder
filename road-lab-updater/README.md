# RoadLab Blender extension and update repository

The full RoadLab 0.17.0 addon is integrated here, including lane markings and quad terrain. Requires Blender **5.1 or later**.

## Install once

1. Save your project. Disable the older **RoadLab** legacy addon in Preferences > Add-ons, then restart Blender. The legacy addon and extension register the same tools and must not run together. Existing project data is retained.
2. Enable **Allow Online Access** in Preferences > System if it is disabled. Then Preferences > Get Extensions > Repositories > Add Remote Repository. Paste:
   `https://raw.githubusercontent.com/hitxne/world-builder/feature/road-lab-updater/road-lab-updater/dist/stable/index.json`
3. Name it RoadLab and enable **Check for Updates on Startup**. Refresh repositories, find **RoadLab**, and install it from this repository.
4. RoadLab > Updates shows the startup check setting and opens Get Extensions. Blender checks for newer versions; use its Update action to install them. This is not a silent forced updater.

Do not first install this ZIP into a different local repository and then install a second copy from the remote feed. Install from the RoadLab remote repository so Blender can associate the addon with its update source.

## Release workflow

`extension/` is the canonical source for this branch. `extension/RoadLab/` contains the working addon; `extension/updates.py` integrates Blender repository settings. The addon data identifiers remain unchanged so previous .blend scenes keep their authoring data.

For each release, increase **both** `extension/blender_manifest.toml`'s version and `extension/RoadLab/__init__.py`'s addon version. Test compatibility before committing. Blender detects updates only when the feed lists a higher compatible version.

Push source changes to `feature/road-lab-updater`. The GitHub workflow validates/builds the ZIP and commits the generated `dist/stable/index.json` and archive to this branch. The public raw GitHub path hosts both. Generated feed commits do not retrigger the workflow. If branch protection blocks the workflow push, publish the generated files through a reviewed PR instead. No tokens ship in the addon.

Build locally:

```sh
BLENDER=/path/to/blender bash road-lab-updater/tools/build_repository.sh
```

Rollback: disable/remove the extension, then install a previous archived package after backing up the project. Repository checks do not edit project files.
