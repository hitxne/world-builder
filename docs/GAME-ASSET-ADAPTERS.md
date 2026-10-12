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
