// font_viewdata_gen.c
// Utility to generate a full Viewdata/Prestel font bitmap (8x10, 256 chars) as a C array.
// This is for development only; not part of the firmware build.
#include <stdio.h>
#include <stdint.h>
#include <string.h>

// Simple 8x10 ASCII font (subset, for demo; replace with real font for production)
uint8_t ascii_font[96][10] = {
    // Space (0x20)
    {0,0,0,0,0,0,0,0,0,0},
    // '!' (0x21)
    {0x18,0x18,0x18,0x18,0x18,0x00,0x18,0x00,0x00,0x00},
    // ... (fill in all ASCII chars 0x20-0x7E)
};

// Generate mosaic block patterns for 0x80-0x9F
void gen_mosaic(uint8_t *buf) {
    for (int i = 0; i < 32; ++i) {
        int ch = 0x80 + i;
        // Each bit: 0x20 top left, 0x10 top mid, 0x08 top right, 0x04 bot left, 0x02 bot mid, 0x01 bot right
        uint8_t pat[10] = {0};
        if (i & 0x20) pat[0] = pat[1] = 0xC0; // top left
        if (i & 0x10) pat[0] |= 0x30, pat[1] |= 0x30; // top mid
        if (i & 0x08) pat[0] |= 0x0C, pat[1] |= 0x0C; // top right
        if (i & 0x04) pat[5] = pat[6] = 0xC0; // bot left
        if (i & 0x02) pat[5] |= 0x30, pat[6] |= 0x30; // bot mid
        if (i & 0x01) pat[5] |= 0x0C, pat[6] |= 0x0C; // bot right
        for (int row = 0; row < 10; ++row)
            buf[(ch*10+row)*8] = pat[row];
    }
}

int main() {
    uint8_t font[256][10] = {{0}};
    // ASCII 0x20-0x7E
    for (int ch = 0x20; ch <= 0x7E; ++ch)
        memcpy(font[ch], ascii_font[ch-0x20], 10);
    // Mosaic blocks 0x80-0x9F
    gen_mosaic((uint8_t*)font);
    // Output as C array
    printf("static const unsigned char __in_flash(\".font\") font_viewdata_bmp[8*10*256] = {\n");
    for (int ch = 0; ch < 256; ++ch)
        for (int row = 0; row < 10; ++row)
            for (int col = 0; col < 8; ++col)
                printf("0x%02X,", (col==0)?font[ch][row]:0);
    printf("\n};\n");
    return 0;
}
