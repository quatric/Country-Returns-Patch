# Country Returns Patch

Play **Donkey Kong Country Returns** on the Wii with a **GameCube controller**
(no Wii Remote or Nunchuk needed), or with a **Classic Controller** that has
full analog movement. Works with the USA (`SF8E01`, Rev 0 and Rev 1), European
(`SF8P01`) and Japanese (`SF8J01`, Rev 0 and Rev 1) releases.

The patch is applied to your own copy of the game: drop a clean `.wbfs` or
`.iso` onto the patcher, tick what you want, and play the result on a Wii (USB
loader) or in Dolphin. Nothing from the game is included in this repository.

## Controllers

- **Classic Controller**: Vague Rant and crediar's analog Classic Controller
  hack, applied straight to the game's `main.dol`. The Classic Controller is
  recognised as a Wii Remote and Nunchuk, so the left stick moves, and it can be
  switched to the plain sideways Wii Remote layout in game.
- **GameCube controller**: new in this patch. A pad in port 1 plays player 1 and
  a pad in port 2 plays player 2. The patch turns the pad into a Classic
  Controller, so every control below is the Classic Controller's, and the game
  needs no Wii Remote at all. If a Wii Remote is connected, it keeps the
  channel and the pad is ignored. Unplug the pad and, after a second, the game
  is told the controller was disconnected, as it would be for a Wii Remote.

### GameCube controller

| GameCube | Action in game |
| --- | --- |
| Control stick | Move / menu navigation |
| A, X | Jump / confirm |
| B, Y | Roll, ground pound, blow (the Wii Remote shake) |
| R, Z | Grab / cancel |
| L | Grab / zoom out on the world map |
| D-pad | D-pad (menus and the plain Wii Remote layout) |
| Start | Pause (+) |
| Z + Start | Plus and Minus together: switch between the Nunchuk and the plain Wii Remote layout |
| L + R + Start | HOME button |

The title screen asks for "A and B": that is A plus R (or Z) on the GameCube
controller.

### Classic Controller

This is Vague Rant's mapping, which matches *Donkey Kong Country Returns 3D* and
*Tropical Freeze*:

| Classic Controller | Action |
| --- | --- |
| Left stick | Move / menu navigation |
| A, B | Jump / confirm |
| R, ZR | Grab / cancel |
| L, ZL | Grab / zoom out on the world map |
| X, Y | Shake: roll, ground pound, blow |
| + / − | Pause / (in menus) copy and delete saves |
| + and − together | Switch between the Nunchuk and the plain Wii Remote layout (per player) |
| HOME | HOME button |

In the plain Wii Remote layout the D-pad moves, 1/2 become L/R (grab) and B/A
(jump), and A zooms the world map out.

## Installing

### Patch your disc image

You need a clean `.wbfs` or `.iso` of the **USA** (`SF8E01`), **European**
(`SF8P01`) or **Japanese** (`SF8J01`) release and
[Wiimms ISO Tool](https://wit.wiimm.de/) (`wit`) on your `PATH` (the downloadable
apps bundle it).

```bash
python3 tools/gui.py
```

Tick *GameCube controller* (the Classic Controller code is always included, the
GameCube controller is built on it), then drop the image onto the window (or
click to choose it). The patcher checks the disc ID, patches `sys/main.dol`,
rebuilds the image in the same format, and replaces your file, keeping the
original next to it as `<name>.bak`. Other versions, and images that are already
patched, are refused rather than corrupted.

### Play on a Wii

Copy the patched image to your USB loader's drive as usual. In the loader's
settings for this game, turn the **debugger, hook type and cheats off**: the
loader's cheat code handler loads into the same memory as the patch and
black-screens the game. The HOME Menu still wants a Wii Remote to steer it, since
a GameCube controller has no pointer.

### Play in Dolphin

Boot the patched image, set GameCube Port 1 (and 2) to *Standard Controller* or
an adapter. No emulated Wii Remote is needed. (If you drive the pad from a script
or a pipe, turn on *Background Input*.)

### Riivolution (no disc patching)

`Country-Returns-Riivolution.zip` from the releases page (or `riivolution/sd/` in
this repo): copy its contents to the root of your SD card. Start the game from
Riivolution and choose *GameCube controller + Classic Controller* or *Classic
Controller only*. The patch writes its code to `0x80001820` from a file in
`/CountryReturnsPatch` and branches the game into it, so it behaves like the
patched image. I haven't been able to try this one on a console or in Dolphin's
Riivolution loader; the bytes are the ones the patcher puts in the DOL.

### Gecko codes

`codes/<build>.ini` (also `Country-Returns-Gecko-Codes-Classic-Controller.zip`)
are Vague Rant and crediar's Classic Controller codes, ready for Dolphin's
`GameSettings` folder or a USB loader. There is no Gecko code for the GameCube
controller: the code is about 3 KB and a Gecko code handler only has room for
roughly 1.8 KB of codes, so Dolphin and the loaders drop it. Use the patched
image or Riivolution for that.

### Command line

```bash
python3 tools/crpatch.py <retail main.dol> <patched main.dol> [--no-gamecube]
```

## Known limitations

- The Wii Remote wins: while one is connected on a channel, a pad on the same
  port is ignored.
- Without a Wii Remote there is no pointer, so the HOME Menu (L + R + Start on a
  GameCube controller) can't be steered.
- I have only tested the controller code in Dolphin: pad responses fed in by a
  debugger (buttons, both ports, the layout toggle, unplugging) and Dolphin's own
  emulated pad through the real SI path (detection). Reports from a real Wii are
  welcome.

## Building from source

The patcher needs only Python 3 and `wit`. The GameCube half (`src/`) ships
prebuilt in `tools/prebuilt/blobs.json`, checked against its source hash by the
tests. With [devkitPPC](https://devkitpro.org/) installed, `tools/build_blobs.py`
rebuilds it and `tools/make_riivolution.py` regenerates the Riivolution patch.
Run the tests with `python3 -m unittest discover -s tests`.

How the patch works is in [docs/TECHNICAL.md](docs/TECHNICAL.md).

## Credits

- **Vague Rant** and **crediar** for the Classic Controller Gecko codes for
  *Donkey Kong Country Returns*, which this patch applies unchanged and which
  the GameCube controller support builds on.
- The SI poller comes from [Barrel-Blast-Patch](https://github.com/quatric/Barrel-Blast-Patch),
  and the idea of feeding the pad in as a Classic Controller sample from
  [ACCF-Patch](https://github.com/quatric/ACCF-Patch).
- Gecko code format and code handler by the Gecko / WiiRD community.

## Contact

quatricsoftware@gmail.com

No support will be provided for this tool.

## License

MIT — see [LICENSE](LICENSE).

Copyright (c) 2026 quatric
