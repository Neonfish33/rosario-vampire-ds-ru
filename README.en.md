# Rosario+Vampire DS — Russian localization (EN)

Russian translation of **Rosario to Vampire: Tanabata no Miss Youkai Gakuen**
(Nintendo DS), based on jjjewel's English fan patch.

This repository contains **only the translation, tools and documentation**.
The game ROM, font binaries and screenshots are not distributed; build from
your own legal copy.

## Done

- 13,858 dialogue lines (9 MPC files) translated and inserted.
- Cyrillic (66 glyphs) embedded into the game's `#FNT` font.
- Line wrapping recalculated for the 228 px text box.
- A ROM was built and tested (not included).

Limitations: speaker name plates stay Latin; menus (Start/Gallery/Options) are
in separate containers and were not translated; some long lines were shortened.

## Layout

```
translation/        Russian 000.txt…008.txt + glossary
tools/              font builder, MPC packer, ROM builder
font/cyr_slots.tsv  char -> glyph slot map
tools/rosario.tbl   codec table (code <-> character)
docs/ENGINEERING.md formats and reverse-engineering notes (RU)
```

Challenges and reverse-engineering notes (RU): [docs/CHALLENGES.md](docs/CHALLENGES.md).

## Build

Requirements: Python 3 (Pillow, ndspy) and the original English ROM placed as
`rosario_eng.nds` in the repository root.

```bash
python tools/extract_mpc.py           # ROM -> work/orig_mpc/*.mpc
python tools/prepare_txt.py           # translation/ -> extracted/mpc
python tools/pack_ru_mpc.py           # -> extracted/mpc/*_ru.mpc
python tools/build_cyr_font7_thin.py  # -> font/font_all_ru7.fnt
python tools/build_rom_v4.py          # -> roms/Rosario_RU_v4.nds
```

## Credits

- jjjewel — English translation and format research.
- tehwes — Rosario Tool (BB/BAC/MPC) and file-format notes.
- DarthNemesis — NFTRedit, BatchLZ77.

## Legal

Game assets belong to their owners. The translation was made by the project
contributors. No ROM or game assets are distributed. Tool code is MIT
(see LICENSE); third-party utilities retain their authorship.
