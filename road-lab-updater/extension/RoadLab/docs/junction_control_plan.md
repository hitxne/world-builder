# Junction control — future plan only

User instruction2026-10-14: do not build traffic-light timing/simulation yet; keep this in notes.

Selected junction editor will offer all-way stop, priority road with stopped/yielding minor approaches, signalized and uncontrolled modes. Per-approach controls explicitly define stop/yield/free-flow; free-flow does not imply collision immunity or unconditional permission. Stop bars/yield decals derive from actual control assignment. Signals will reference permitted/protected/permissive movement groups and pedestrian/bicycle conflicts.

Later signal system: configurable green/yellow/all-red phases, movement conflict validation, shared simulation clock, corridor IDs and phase offsets for neighboring junction coordination, optional later traffic-demand detection. Changing control mode should be previewed/undoable. Timings and legal presets require source verification; do not hardcode generic durations as legal defaults. No signal controller implemented or promised in the current marking pack.
