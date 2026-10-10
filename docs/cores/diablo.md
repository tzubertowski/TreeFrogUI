# Diablo 1 (DevilutionX)

This integration is packaged from [FroggyDiablo](https://github.com/tzubertowski/FroggyDiablo),
based on the original [DevilutionX project](https://github.com/diasurgical/DevilutionX).

TreeFrogUI launches the standalone DevilutionX port from **Games → Diablo 1**.

This package does not include Blizzard's copyrighted game data. Copy the
`DIABDAT.MPQ` file from your legally owned Diablo 1/GOG installation into:

```text
/roms/diablo/DIABDAT.MPQ
```

The release includes the open-source `devilutionx.mpq` engine asset and the
`Start Diablo 1.diablo` launcher. Select it after copying `DIABDAT.MPQ`; the
launcher sets the working directory so DevilutionX can find the data and save
files beside it.

The SF3000 test build is based on the C++17-compatible DevilutionX revision
used by the device's GCC 6.3 toolchain.
