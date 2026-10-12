# Automatic Sims catalog organization

The shared exporter reads COBJ tags, joins a unique OBJD by instance, reads its model property list, follows MODL LOD references, and attaches tags to the matching exported MLOD key. No filename/category guessing or arbitrary binary tag scanning. Source packages remain read-only.

Select Add Sims assets and choose the game EXE again after updating. Existing OBJ files are kept while `.obj.catalog.json` sidecars are regenerated. Existing library entries retain their identity, meshes, placements and thumbnail cache; the import refreshes metadata in place. Manual organization overrides survive refresh; Organize asset > Use decoded Sims categories restores automatic labels.

Room tags map to Living room, Bathroom, Bedroom, Dining room, Kitchen, Outdoors and Office. Supported function tags map to seating, tables, beds, storage, lighting, decor, doors, windows, plants, plumbing, appliances, electronics and activities. All known matching rooms/types remain searchable, rather than forcing an object into one category. Unknown numeric tags and source catalog keys are retained for future mappings. COBJ NameHash is resolved through English STBL v5 UTF-8 records (locale prefix 00), so cards and newly placed objects use the game’s displayed name. Only requested catalog-name hashes are retained in memory. Identical duplicate strings are accepted; conflicting values are reported and excluded. Missing/conflicting strings fall back to OBJD internal names, then resource filenames. Manual labels remain unchanged. Other languages and internally compressed STBL payloads are not yet supported.

## Bounds and coverage

COBJ CommonBlock versions 1–11 use version-specific 16/32-bit tags and style/pack fields. OBJD property tables and swapped-instance ITG model lists are bounded. RCOL 3 MODL versions 256, 257, 258 and 0x300 are supported. Unknown versions, missing dependencies and duplicate resource keys are reported as catalog-unlinked; patch precedence is not inferred. Shared meshes aggregate tags from their validated catalog records. Objects without supported tags remain Unclassified. This does not add procedural floor/wall catalog export, textures, swatch assembly or full current-game coverage.

## Format references

Independently written readers use binary field layouts documented by the Sims4Tools maintainers at commit `fff19365a12711879bad26481a393a6fbc62c465`:

- https://github.com/s4ptacle/Sims4Tools/blob/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/CatalogResource/CatalogCommon.cs
- https://github.com/s4ptacle/Sims4Tools/blob/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/CatalogResource/ObjectDefinitionResource.cs
- https://github.com/s4ptacle/Sims4Tools/blob/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/MeshChunks/MODL.cs
- https://github.com/s4ptacle/Sims4Tools/blob/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/StblResource/StblResource.cs
- https://github.com/Llama-Logic/Binary-Templates/blob/main/README.md (STBL locale-prefix convention)
- https://github.com/s4ptacle/Sims4Tools/blob/fff19365a12711879bad26481a393a6fbc62c465/s4pi.Resource.Commons/S4_03B33DDF_00000000_D89CB9186B79ACB7.xml

No s4pi library or implementation code is included. The small tag mapping uses numeric format identifiers, not game assets.

## Verification

The actual shared exporter is compiled with Roslyn and exercised with original synthetic DBPF fixtures: UTF-8 game display names, legacy/modern tags, multi-room/type classification, raw unknown-tag preservation, catalog-definition-model-mesh linkage, unsupported versions, resume metadata refresh, immutable source files and existing geometry. These do not establish coverage for Josh's installation; that requires a native import and its catalog-unlinked report. Unity source/config checks are separate from compilation and visual verification.
