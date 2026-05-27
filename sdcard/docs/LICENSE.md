# License and Attribution

This project is a compilation of multiple components, each retaining its original license terms.

---

## 1. TreeFrogUI Frontend Code

The TreeFrogUI frontend (located in the `frogui/` subdirectory and built as `frogui_libretro.so`) is a heavily modified fork of **FrogUI** (github.com/tzubertowski/frogui). It is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** License.

Copyright (c) 2024-2025 FrogUI Contributors:
- Tomasz Zubertowski (tzubertowski @ GitHub, Prosty @ social media/Discord)
- Desoxyn (Trademarked69 @ GitHub)
- Q_ta (Q_ta_s @ social media, https://github.com/Q-ta-s)

### Key Terms of CC BY-NC-SA 4.0:
- **Attribution**: You must give appropriate credit to the original FrogUI contributors, provide a link to the license, and indicate if changes were made.
- **NonCommercial**: You may not use this material for commercial purposes. This includes selling FrogUI or bundling it with hardware devices for sale.
- **ShareAlike**: If you remix, transform, or build upon this material, you must distribute your contributions under the same CC BY-NC-SA 4.0 license as the original.
- **No additional restrictions**: You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.

To view a copy of this license, visit: http://creativecommons.org/licenses/by-nc-sa/4.0/

*Notice: FrogUI is built upon libretro, which is licensed under GPLv3. The libretro components retain their original GPL licensing. This CC BY-NC-SA 4.0 license applies to the original FrogUI code and creative works.*

---

## 2. Picoarch Frontend Wrapper

Picoarch (the backend integration wrapper used to load cores and manage display output) is licensed under a mix of licenses:
- Code from `libpicofe` is triple-licensed: GNU GPL v2 or later, GNU LGPL v2.1 or later, and the MAME license.
- The remainder of the picoarch code is licensed under the **BSD 3-Clause License** by neonloop:

```
Copyright 2021 neonloop

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

---

## 3. Emulator Cores

All emulator cores contained or cloned into the `cores/` directory are built from separate upstream source repositories. They are governed by their respective individual open-source licenses (GPL, LGPL, BSD, MIT, MAME, etc.). Please refer to the documentation or source files within each core's directory, or see [cores.md](cores.md) for links to the upstream repositories.
