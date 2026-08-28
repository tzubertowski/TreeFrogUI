TOOLCHAIN ?= /home/tomaszz/sf3000-work/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot
CROSS     := $(TOOLCHAIN)/opt/ext-toolchain/bin/mips-mti-linux-gnu-
SYSROOT   := $(TOOLCHAIN)/mipsel-buildroot-linux-gnu/sysroot
CC        := $(CROSS)gcc

CFLAGS := -mips32r2 -march=mips32r2 -mtune=24kc -mfp32 -mhard-float -mlong-calls \
          -EL --sysroot=$(SYSROOT) -G0 -Os -Wall -Wextra -I$(SYSROOT)/usr/include
LDFLAGS := -mips32r2 -mhard-float -mfp32 -EL --sysroot=$(SYSROOT) -L$(SYSROOT)/usr/lib

FONT_SOURCE := ../../../picoarch/libpicofe/fonts.c
TARGET := ../../sdcard/cubegm/video_player

.PHONY: all clean
all: $(TARGET)

$(TARGET): video_player.c $(FONT_SOURCE)
	$(CC) $(CFLAGS) video_player.c $(FONT_SOURCE) $(LDFLAGS) -Wl,--gc-sections -lffplayer -ljpeg -lpthread -o $@
	$(CROSS)strip $@

clean:
	rm -f $(TARGET)
