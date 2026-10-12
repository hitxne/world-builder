# Local Sims package-to-OBJ batch exporter

This standalone .NET 8 command-line tool reads installed DBPF packages and exports supported object MLOD geometry. It does not require Unity or The Sims 4 to be running. Source packages are read-only. Output must be outside the installation/package folder.

## Normal in-app workflow — select one EXE

Click **Add Sims Assets** in the World Builder navigation bar (also available in Local Library), then select TS4_x64.exe or TS4_DX9_x64.exe. The app locates the installation via Data/Client, remembers the path, runs extraction in the background into its local data directory and automatically imports exported OBJ files into the library. Progress and cancellation are available. No .NET SDK, output-folder selection or separate exporter launch is required for this in-app route.

The one-step interface is implemented but not tested in Unity/Windows here. Supported geometry-only limitations below still apply; selecting the EXE does not imply complete catalog or texture support.

## Advanced standalone CLI on Windows

Requires the .NET 8 SDK. From the checked-out World Builder repository in PowerShell:

```powershell
$simsInstallFolder = Read-Host 'Sims 4 installation or package folder'
$simsObjExportFolder = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WorldBuilder\SimsExports'
dotnet run --project tools/sims-export/SimsExport.csproj -- "$simsInstallFolder" "$simsObjExportFolder"
```

CTRL+C stops after the current bounded resource operation. Completed OBJ files remain. Running again skips existing output; use a fresh output folder when source packages change. The output can be ingested through Local Library > Import Sims export folder.

OBJ files are grouped by a hash of each source package's relative path. A JSONL report records source package/resource keys, success, unsupported layouts, failures and a summary. Exit code 0 means no MLOD decode failures encountered, 1 means partial failures, 2 means a fatal/input error, and 130 means cancellation. Code 0 does not establish complete Build/Buy coverage, including when no candidates exist.

## Verified coverage and limitations

The exporter processes object MLOD resources, with catalog associations when COBJ → OBJD → MODL → MLOD links can be validated. A .obj.catalog.json sidecar contains raw tags, catalog keys, supported room/type labels and the English STBL game display name (OBJD internal name fallback). Resume refreshes sidecars for existing geometry. It can export multiple mesh parts into one OBJ and resolve unique cross-package buffer dependencies. Patch precedence and ambiguous duplicate dependencies are not guessed; they are reported as unsupported. Package copies/LODs may therefore appear separately.

Current support is DBPF 2.1, the previously implemented bounded compression reader, RCOL 3, MLOD 0x201–0x204, supported static position layouts and triangle-list indices. Differenced/collapsed buffers and unsupported record layouts are rejected. UVs, normals, materials, textures, swatch mapping, other-language STBL names, full MODL visual assembly and procedural walls/floors/roof systems are not decoded. The OBJ header/report explicitly identify geometry-only output; no invented texture maps or materials are written.

**This is not yet an exporter for every Sims Build/Buy asset.** Real installation coverage has not been measured. No installed game files are available in this cloud environment. The continuation is to use the report to identify actual layouts, implement/verify missing decoders, link catalog/MODL/LOD/material resources, resolve verified patch ordering and test representative textured objects before claiming complete coverage.

## Tests executed

Actual exporter/decoder/package C# source compiled with Roslyn 4.11 and executed on .NET 8.0.15. Original synthetic-package integration checks passed: valid triangle OBJ, explicit unsupported resource report, resume without duplicates, byte-identical sources, rejected output inside the game folder and no temporary-file residue.

Run the integration checks against a built DLL:

```text
python tools/sims-export/test_export.py dotnet tools/sims-export/bin/Debug/net8.0/SimsExport.dll
```

Unity preview adapter compatibility has only been source/syntax checked. Existing Unity EditMode decoder regressions still require Unity. Unique cross-package resolution also passed a synthetic multi-package triangle test; real package layouts and patch resolution remain unverified.

## Format research

Original decoder format references are documented in docs/GAME-ASSET-ADAPTERS.md. Relevant published format/library sources:

- https://modthesims.info/wiki.php?title=Sims_4%3A0x01D10F34
- https://github.com/s4ptacle/Sims4Tools

No third-party library code or proprietary resources were copied into this exporter. The shared engine-independent reader is factored from this repository's existing implementation. This tool does not establish redistribution permission for exported game content.

Catalog reader support and limitations: see [SIMS-CATALOG-DECODING.md](../../docs/SIMS-CATALOG-DECODING.md).
