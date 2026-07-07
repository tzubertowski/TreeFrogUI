# DOS / PC games (pico286)

← [back to README](../../README.md)

`pico286` runs old DOS / PC games (the 8086 to 286 era: Prince of Persia, Digger, Oregon Trail, etc). Games go in `roms/pico286/`.

**Step 1 (do this once): give it FreeDOS.**
A ready-made FreeDOS file already ships with TreeFrogUI at `cubegm/bios/x86BOOT.img`, so you usually do nothing. If it is missing: download the **FreeDOS 1.4 "Floppy Edition"** from [freedos.org/download](https://www.freedos.org/download/), open the zip, take the file **`144m/x86BOOT.img`**, and copy it to **`cubegm/bios/x86BOOT.img`** on the card. (FreeDOS is the little operating system the games run on top of. You only set this up once.)

> The bundled boot image is **FreeDOS** + the **CuteMouse** driver, both GPLv2. Full credits, license, and source links: [freedos.org](https://www.freedos.org/) and `roms/pico286/CREDITS-FREEDOS.txt` in the release.

**Step 2: add a game. The easy way (no tools, works on any computer):**
1. Get the game as **floppy disk images** (files ending in `.img`).
2. Make a folder for it, like `roms/pico286/prince/`.
3. Copy the `.img` files into that folder.
4. Launch it from the menu. It boots FreeDOS and starts the game by itself.

That's it. Most DOS games come as one or a few floppy `.img` files and just work this way.

**Multi-disk games:** if a game asks to "insert disk 2", press **SELECT + START** for the menu, choose **Disk swap**, pick disk 2, press A. Then continue in the game.

**Big games that need a "hard disk" (optional, advanced):**
Some bigger games come as loose files (an `OREGON.EXE` and friends), not floppies. For those you pack the files into one hard-disk image. Make a folder with all the game files, add a text file named `RUN.BAT` inside it containing the command to start the game (for example one line: `OREGON`), then build the image:

- **Linux / macOS:** run the included script (needs `mtools` installed):
  ```
  ./make_dos_img.sh  <game_folder>  oregon.img  16
  ```
- **Windows:** the script does not run on Windows directly. Easiest options:
  1. **WSL** (Windows Subsystem for Linux): install it, `sudo apt install mtools`, then run the same `./make_dos_img.sh` command above. Recommended.
  2. **DOSBox** (works everywhere): `imgmake oregon.img -t hd -size 16`, then mount it and copy the game files in. See DOSBox docs for `imgmake`/`mount`.
  3. Any tool that can **make a FAT16 disk image** and copy files into it (e.g. WinImage: New image, 16 MB, format FAT16, drag the files in, Save As `.img`).

Drop the resulting `oregon.img` into `roms/pico286/oregon/` and launch it.

**Controls / menu:**
- **SELECT + START** - open the pico286 **main menu**: Resume, Keyboard, Disk swap, Mouse mode, Mouse speed, Joystick mode, CPU speed, Frame skip, Reset, Exit to menu. (D-pad navigates, A selects, Left/Right adjusts the speed/skip rows, B closes.)
- **Joystick mode** (menu toggle): D-pad → game-port axes, A/B → joystick buttons 1/2.
- **L + R** - quick on-screen keyboard (D-pad moves, A presses, B closes) for typing DOS commands.
- **Mouse mode** (toggle in the menu): D-pad moves the cursor, A = left click, B = right click. Needs a mouse driver, which the bundled FreeDOS loads automatically (CTMOUSE).
- In-game buttons: A=Enter, B=Esc, X=Space, Y=Ctrl, L=Shift, R=Alt.
