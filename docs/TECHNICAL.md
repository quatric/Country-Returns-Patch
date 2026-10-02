# Technical notes

How the patch works, where it hooks, and how it was checked. For installing and
playing, see the [README](../README.md). Addresses are USA Rev 1 unless noted;
the other builds are found by `tools/anchors.py` (see "Other builds").

## The idea

The Classic Controller half is Vague Rant's and crediar's Gecko codes, applied
unchanged: the game gets a Wii Remote reporting a Classic Controller, and the
hooks turn that into a Wii Remote plus Nunchuk (or a plain Wii Remote).

The GameCube half does not touch any of that. It makes a GameCube pad look like a
Classic Controller to the KPAD library, and the existing hooks do the rest:

```
GC pad --SI hardware--> SICnINBUFH/L --[gc_update]--> KPAD sample ring (a Classic Controller sample)
                                                           |
                                    KPADRead --> Vague Rant's hooks --> game
```

## Hooks (all in `main.dol`, via one extra text section at `0x80001820`)

| Site | What | Job |
| --- | --- | --- |
| `0x80386F60` | the game's per-frame controller update (a virtual method of the controller manager; `r3` = manager) | run the SI poller for the four ports, then `gc_update()` |
| `0x804CAE80` | `WPADProbe(chan, &type)` | with no remote and a pad answering, report "connected, Classic Controller" |

Both are the first instruction of a function, `stwu r1,-N(r1)`. The wrapper
(`src/wrappers.s`) saves `r3`-`r31`, CR, CTR and LR on its own frame, calls into
the patch, restores everything, runs the replaced `stwu` and jumps back to the
site + 4 through `r0`/CTR. The code is position independent (linked at 0, no
relocations), so the same words work in the DOL and in Riivolution.

### Why the update hook, not `KPADRead`

The game calls `KPADRead` (`0x804A8550`) from exactly one place, the controller
update, and only for a channel whose controller state is "connected". With no
Wii Remote nothing ever marks the channel connected, so `KPADRead` is never
called and a hook in it never runs. The update runs every frame regardless.

## The SI poller (`src/poller.s`)

The game links the `si::` library but not `PAD`, so nothing polls the pads and
`SICnINBUFH` stays empty on a real console. The poller is Barrel Blast Patch's:
it writes the poll command into every `SICnOUTBUF`, latches it with a `SISR`
write (WR set, error bits acknowledged), enables polling and copy-on-vblank in
`SIPOLL` for channels whose cached `si::` type is a standard pad, mirrors that
into `si::`'s own `SIPOLL` shadow (`0x8059217C`, which `SISetXY` rewrites on every
retrace), probes empty ports with `SIGetType` at most every 0.25 s, copies a
persistent NOREP into the type cache so a replugged pad is probed again, and
unwedges `si::`'s global busy flag if it stays busy for a second. SI addresses
are the Wii's, `0xCD00xxxx`: Dolphin mirrors `0xCC`, a console does not.

`si::` addresses in the game: busy flag `0x80592178`, `SIPOLL` shadow `+4`,
per-channel types `+0x18` (`0x80592190`), `SIGetType` `0x804BEC90`,
`OSDisableInterrupts` `0x804B6F30`, `OSRestoreInterrupts` `0x804B6F70`.

## Pad to Classic Controller sample (`src/gcpad.c`)

`gc_update()` runs per channel (0 and 1; the game has two players).

1. A real Wii Remote (`WPADProbe` would say connected) owns the channel: do
   nothing.
2. No pad answering: if the pad had been connected, after one second of silence
   tell the game it went away.
3. Pad answering, first time: do what the WPAD library does when a Classic
   Controller connects. Call the game's connect callback (stored by the KPAD
   library at channel state `+0x63C`) with `0`, then the game's WPAD extension
   callback (`0x80389AC0`) with `(chan, 2)`. The extension callback must be
   called with `r12` pointing at itself, which is what a callback invoked through
   a pointer does and what Vague Rant's hook on it relies on to find its
   per-player controller-mode byte, so `gc_update` calls it from inline assembly.
4. Queue one sample in the KPAD sample ring of the channel (`kpad_base + chan *
   0x688`; ring at `+0x180`, 0x42 bytes per sample, write index `+0x17A`, count
   `+0x17B`, extra ring pointer `+0x5A0`):

   | Offset | Value |
   | --- | --- |
   | `+0x28` | `2`, extension: Classic Controller |
   | `+0x29` | `0`, no extension error |
   | `+0x2A` (u16) | Classic Controller buttons |
   | `+0x2C`, `+0x2E` (s16) | left stick, `(byte - 128) * 3` clamped to +-308 |
   | `+0x30`, `+0x32` (s16) | C-stick, same scaling |
   | `+0x34`, `+0x35` | analog L / R, `180` or `0` (the game reads them as buttons) |
   | `+0x40` | `8`, data format |

   KPAD's pad-side dead zone is 60 counts of that scale, 20 raw counts.

`gc_probe()` (the `WPADProbe` hook) answers `0` with `*type = 2` when there is no
remote on the channel and a pad is answering. `KPADRead` returns early with an
error when `WPADProbe` says there is no controller, so this is what lets it read
the sample ring at all.

The pad's buttons map to Classic Controller buttons as in the README; see
`cc_buttons()`.

## Other builds

The code is written once against USA Rev 1 and found in the others by
`tools/anchors.py`: a window of USA instructions is matched against the target
`main.dol` with branch displacements, address halves and load/store offsets
masked out, and must match exactly once. Data addresses (si state, KPAD state,
WPAD control block table) are read back from the matched code's `lis`/`addi`
pairs. The Japanese Rev 0 and Rev 1 discs carry byte-identical `main.dol`s.
`tools/regions.py` holds the result.

## Testing

`tools/build_blobs.py --debug` builds a variant whose pad response is read from
the patch's scratch area (`+0x40 + 8 * chan`) instead of the SI registers.
`tools/dev/` boots a patched image in Dolphin with no Wii Remote, writes pad
responses over Dolphin's GDB stub, and reads the KPAD status back
(`press_test.py`) or saves frames (`play.py`). Dolphin's emulated SI proves
detection but not presses, which is why the debugger feed exists.

`python3 -m unittest discover -s tests` needs no game files.
