# training/specs

Source specifications for the autonomous E4B track, adopted under the
competition contract. They are upstream input, not the operative plan: where a
line conflicts with a measured raw artifact, the artifact wins. The operative
scope is `odd/tasks/autonomous-e4b.md` and issue #180.

| File | Upstream id | Status | What it says |
|------|-------------|--------|--------------|
| `gemma-4-e4b-autonomous.md` | G4-PY-AGENT-001 | adopted with scope cuts | Full autonomous Python agent specification |
| `rtx3090-hardware-profile.md` | G4-PY-AGENT-001-HW3090 | adopted with the measured 10240 override | Single RTX 3090 hardware profile |

The files are kept verbatim so every decision in the tracker can be audited
against the source. Do not edit them to match the implementation; record a
decision in the tracker instead.
