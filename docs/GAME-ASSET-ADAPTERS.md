# Read-only game preview adapters

This is an implementation increment, not verified full-game integration. Real game
files are unavailable in the cloud environment. Actual installed assets must be
validated on the user's PC. No encrypted archive reader or decryption is included.

## Source research

- Sims DBPF 2.1 reference (Fogity):
  https://thesims4moddersreference.org/reference/dbpf-format/
- RCOL/MLOD/VRTF/VBUF/IBUF wire fields inspected in Kuree/Sims4Tools at
  `f50d697a8a1c4289c3a1f607add51cf214e4ee8d`. Repository is deprecated; successor
  is s4ptacle/Sims4Tools. No upstream GPL code/binaries were copied or linked.
- Forza Grub/Mesh/VLay/BufferHeader inspected in D3FEKT/ForzaTechStudio at
  `4f373c5fb192551ce5249e320dd79b1399b693ca`. MIT attribution is retained in
  THIRD_PARTY_NOTICES.md. Upstream notes that FH5 encrypted archives need a separate
  workflow; this project does not implement or invoke decryption.

Unity handles rendering after decoded geometry is converted into native Mesh and
Material objects. Porting the games' renderers is not necessary for this viewer.
Correct material/shader translation is separate from static mesh decoding.

## Implemented, pending real-file validation

### Sims
- DBPF 2.1 index parsing with shared key fields, 64-bit index location, resource bounds.
- Read-only raw and zlib resources, bounded inflate and Adler-32 verification.
- Resource selection by MLOD instance ID.
- RCOL v3 local/private references and same-package external dependencies.
- MLOD 0x201–0x204 triangle-list buffers.
- Float3/float4 and selected short4 position encodings, absolute vertex streams.
- 16/32-bit absolute/differenced indices. Normals generated for neutral geometry
  previews. Source UVs/textures/materials are NOT reconstructed by this adapter.

Not implemented: cross-package dependency graph, CAS GEOM, collapsed/differenced
vertex streams, internal compression, source normals/UVs, material links, diffuse/
normal textures, full object catalog names/thumbnails. A large game package may
contain dependencies in other packages and will report that preview limitation.

### Forza
- Plain Grub container 1.0/1.1 directory and Name/Id metadata.
- Mesh versions 1.8–1.10 with bounded buffer references, triangle-list topology.
- Float3/float4 and SNORM16x4 positions, mesh scale/translate, index draw offsets,
  16/32-bit index buffers and vertex stream offsets.
- Neutral, local-part geometry preview. This is not assembled car or environment
  rendering. Bone transforms, skinned meshes, other packed layouts, morph blending,
  UVs/normals/materials/textures and newer mesh versions remain unsupported.

Not implemented: encrypted game archives, LZX/MiniZip archive reader, carbin scene
assembly, swatchbin textures and materialbin shader translation. Installed FH5 may
expose no directly readable modelbins until a supported external workflow exists.

## Using the browser

Game Asset Browser > choose/type installation folder > Scan. Select a Sims package
or plain Forza modelbin > select an MLOD/mesh resource. The adapter attempts a real
geometry decode, leaves the existing reference intact on failure and reports the
specific limitation. Successful supported geometry appears in the reference pane.
Game-source previews remain read-only; no redistribution/import rights are implied.

## Exposing the environment without uploading the game

Game Asset Browser > Export Game Diagnostic > choose a JSON destination.
Review that JSON and attach it to the conversation. It contains bounded file counts,
relative filenames, sizes, resource type histograms, mesh counts/versions and parser
errors. It includes neither resource bytes nor absolute installation paths. It does
not make the user's drive remotely accessible. The first eight files of each selected
extension are inspected; scanning is bounded and never follows directory symlinks.
It is not an exhaustive inventory or a claim of import compatibility.

If geometry is still unsupported, exact errors plus one small authorized sample
resource may be needed to validate its format. Do not upload whole games or asset
dumps. Local Unity tests and synthetic fixtures can run without game files.

## Verification

Executed: JSON/metadata checks, C# grammar parsing and git diff whitespace checks.
NUnit fixtures added for DBPF shared-index flags, unsupported compression, corrupt
index bounds, inline Sims MLOD triangle decode, unsupported position layout, plain
Forza triangle decode and non-bundle rejection. These fixtures are original synthetic
data; no proprietary game bytes are in the repository.

Unity compilation, NUnit execution, game-file previews and Windows build were NOT
executed here. The environment has no Unity/C# compiler; an attempted compiler
installation was unavailable. Use Window > General > Test Runner > EditMode > Run
All on the user's machine. The preceding workspace must also pass its smoke tests.

## Next acceptance targets

1. Diagnostic report from actual Sims/Forza installation; verify container/version
   distributions and concrete failure modes before widening decoder coverage.
2. Test one known uncompressed and one zlib Sims MLOD; implement cross-package
   dependency resolution and packed VBUF handling from actual sample evidence.
3. Verify Forza local-part coordinates on a known model; add bone assembly, normals/
   UVs and texture previews. Research supported plain/archive workflows separately.
4. Translate material references, show missing dependencies and provenance; retain
   editable master assets and controlled import permissions.

## Diagnostic follow-up from actual metadata — 2026-10-12

The user-provided v1 report scanned 629 Sims packages (full directory scan), but
sampled only ClientDeltaBuild0–7. Seven indexes parsed; those samples contained no
MLOD. ClientDeltaBuild0 failed a resource-bounds check. Upstream package code treats
`0xffffffff` offsets and the size=1/memsize=0xffffffff pattern as deleted resources.
The reader now recognizes those tombstones without invalidating the whole index,
and still refuses to read their nonexistent payloads. This is a candidate fix for
the observed failure, not a verified diagnosis from the metadata alone.

Forza scan stopped at 1500 folders: 20,204 files encountered, 9,624 ZIPs and 8
MiniZips counted, no loose models listed. This is a partial inventory, not proof that
no loose files exist elsewhere. The v1 archive counts of zero did not inspect inside
archives and must not be interpreted as empty archives.

Diagnostic v2 samples eight files per family: Sims FullBuild, DeltaBuild and other;
Forza car ZIPs, track ZIPs and other ZIPs. Standard ZIP central-directory metadata
reports names, compression methods and encryption flags without inflation or
extraction. Nonstandard containers, ZIP64 and custom formats report explicit limits.
MiniZip diagnostics report only a container-signature value; no MiniZip decoder is
claimed. Synthetic tombstone and ZIP-directory NUnit fixtures were added. Cloud
source/grammar checks passed; Unity execution and real-file retry remain pending.

## Actual diagnostic v2 and archive opening increment

The v2 report confirms that car ZIP directories contain model names: Integra has
96 modelbin entries and NSX 97. Reported methods are stored/deflate, with no central
ZIP encryption flags. This does not prove that each payload is readable; plain Grub
magic/version and geometry layout checks still apply after reading selected entries.

World Builder now opens selected ordinary ZIP model entries in memory, with a 64 MB
compressed/expanded bound, explicit compression/encryption rejection and CRC checking.
No installation files are extracted or written. The existing Forza model/mesh
resource browser works against in-memory bundles. ZIP64, MiniZip and custom methods
(including method 22 in other sampled archives) remain unsupported.

Sims tombstone handling alone did not resolve the user's ClientDeltaBuild0 failure.
Some FullBuild packages also fail payload-bounds checks. Instead of aborting the
entire valid resource index, the reader now records exact per-resource metadata
warnings and refuses access to invalid payloads. It accepts zero-size placeholders.
Diagnostic v3 includes offsets, sizes, compression and resource keys for those
warnings, plus empty/invalid-entry counts. The file index remains inspectable so
valid MLOD resources can be located; this is not a relaxed payload-read check.

Local acceptance: Game Asset Browser > Forza folder > Scan >
ACU_IntegraR_01.zip > scene/Exterior/BumperF/bumperF_a.modelbin > mesh preview.
Do not choose the skeleton-only entry. A successful preview is still a neutral
part, not an assembled textured car. Run EditMode tests for ZIP selected-member
read/CRC/encryption rejection and invalid Sims payload isolation. Cloud source and
C# grammar checks passed; these Unity/NUnit/real-file operations have not run here.

For next environment-format research, the user's report lists a small sample:
media/Tracks/homespace02/GeoChunk1.minizip, 258,048 bytes, magic 0x505A4750.
No claim of compatibility or successful decode is made. The sample can be supplied
privately for analysis rather than uploading the much larger Hendrix chunks.
