## Uploading the VersaTerm firmware to the Raspberry Pi Pico

Uploading firmware to the Raspberry Pi Pico is easy:
- Press and hold the button on the Raspberry Pi Pico (there is only one) 
- While holding the button, connect the Raspberry Pi Pico via its micro-USB port to your computer
- Release the button
- Your computer should recognize the Pico as a storage device (like a USB stick) and mount it as a drive
- Copy the [VersaTerm.uf2](VersaTerm.uf2) file to the drive mounted in the previous step

## Building the VersaTerm firmware from source

### Requirements
- CMake 3.12 or later
- GCC (cross-)compiler: arm-none-eabi-gcc

### Getting and building the source

```
git clone https://github.com/dhansel/VersaTerm.git
cd VersaTerm
software/tools/setup-submodules.sh
mkdir software/build
cd software/build
cmake .. -DPICO_SDK_PATH=../lib/pico-sdk -DPICO_COPY_TO_RAM=1
make
```

`setup-submodules.sh` runs `git submodule update --init --recursive` and then reapplies
two local overrides that a plain submodule update strips out again (see comments in the
script for details):

- Bumps `lib/pico-sdk/lib/tinyusb` to TinyUSB 0.18.0 (commit `86ad6e5`) instead of the
  0.12.0 that ships with the pinned pico-sdk version. 0.12.0 has USB keyboard
  enumeration issues through (some) USB hubs, resolved in 0.18.0. This can't be recorded
  as a normal submodule pin because it's nested two levels deep
  (VersaTerm -> pico-sdk -> tinyusb), so it has to be reapplied by hand/script after
  every submodule sync. **If a keyboard stops responding (e.g. hangs on the startup
  screen with no key input) after resyncing submodules, this is almost certainly why —
  rerun the setup script and rebuild.**
- Patches `lib/pico-sdk/tools/FindPioasm.cmake` to add
  `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` to the pioasm sub-builds. Needed with CMake 4.x,
  which refuses to configure the vendored pioasm sources (their `CMakeLists.txt`
  requires CMake < 3.5, support for which CMake 4 dropped entirely). Harmless with
  older CMake.

After running the script, `git status` will show `software/lib/pico-sdk` as having
"modified content" — that's expected and reflects the tinyusb override above, not
something to discard/reset.

### If your ARM toolchain can't find `nosys.specs`

If you have more than one `arm-none-eabi-gcc` installed (e.g. both a Homebrew build and
the official [Arm GNU Toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)),
the one earlier in your `PATH` may be missing `nosys.specs`/newlib support even though
another installed copy has it. Rather than changing your `PATH`, point CMake at the
working toolchain explicitly:

```
cmake .. -DPICO_SDK_PATH=../lib/pico-sdk -DPICO_COPY_TO_RAM=1 -DPICO_TOOLCHAIN_PATH=/path/to/working/arm-none-eabi/bin
```

This should create file VersaTerm/software/build/src/VersaTerm.uf2<br>
Follow the "Uploading firmware to Raspberry Pi Pico" instructions above to upload the .uf2 file to the Pico.

The instructions above will use the of pico-sdk and PicoDVI versions that were
current when I wrote and tested VersaTerm. Building from those sources should result in
the same VerTerm.uf2 file as the one in VersaTerm/software.

If you feel adventurous you can build VersaTerm with the latest versions of the libraries:
```
git clone https://github.com/dhansel/VersaTerm.git
cd VersaTerm/software/lib
git submodule update --init
cd pico-sdk/lib
git submodule update --init
git submodule update --remote --merge
cd ../..
git submodule update --remote --merge
cd ..
mkdir build
cd build
cmake .. -DPICO_SDK_PATH=../lib/pico-sdk -DPICO_COPY_TO_RAM=1
make
```

## Some solutions to compile issues

A big thank you to user [unclouded](https://github.com/un-clouded) who reported a number of compile-time 
issues and their solutions:

When it said to me:

    arm-none-eabi-gcc: fatal error: cannot read spec file 'nosys.specs': No such file or directory

I replied:

    apt install libnewlib-arm-none-eabi

And when it said:

    fatal error: cassert: No such file or directory

I retorted:

    apt install libstdc++-arm-none-eabi-dev

And then it complained that:

    /usr/lib/gcc/arm-none-eabi/12.2.1/../../../arm-none-eabi/bin/ld: cannot find -lstdc++: No such file or directory

And I spake thusly:

    apt install libstdc++-arm-none-eabi-newlib
