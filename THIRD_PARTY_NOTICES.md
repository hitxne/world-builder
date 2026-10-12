# Format research and attribution

## Forza Grub and mesh layout

Forza read-only adapters were developed with reference to the wire layout in
[D3FEKT/ForzaTechStudio](https://github.com/D3FEKT/ForzaTechStudio), pinned for
research to the checkout recorded in docs/GAME-ASSET-ADAPTERS.md. The following
notice applies to that MIT-licensed format implementation and derived layout work:

MIT License

Copyright (c) 2023 Nenkai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Sims format references

DBPF adapter is an independent implementation of the public format specification
by Fogity: https://thesims4moddersreference.org/reference/dbpf-format/.
RCOL/MLOD wire-field research used Kuree/Sims4Tools (deprecated; successor
s4ptacle/Sims4Tools), including GenericRCOLResource and MeshChunks. No s4pi source
files or binaries were incorporated. These upstream implementations are GPL;
World Builder's adapter contains its own bounded binary-reading implementation
and does not link s4pi. Mesh encoding facts and unsupported cases are documented
separately. These sources are research references, not bundled dependencies.

No proprietary Sims, Forza, or other game assets are distributed here. Tooling
licenses do not grant redistribution rights to game content.
