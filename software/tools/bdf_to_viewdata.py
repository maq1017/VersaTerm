#!/usr/bin/env python3
"""
Convert Bedstead-20 BDF font to VersaTerm font_viewdata.h

16-px-native layout: the full 12-px Bedstead glyph is placed into a 16-px
cell (2 px left margin + 12 px glyph + 2 px right gap) and split into two
8-bit bytes per scanline.

Output: 256 characters × 20 scanlines, 1 byte (8 pixels) per scanline.
Layout: 32 chars per row × 8 char-rows = 256 chars total.
Stored in BMP format (upside-down rows) as expected by VersaTerm's set_font_data().

bitmapWidth  = 256  (32 chars × 8 px)
bitmapHeight = 160  (8 char-rows × 20 scanlines)
charHeight   = 20

Character slot layout:
  0x00-0x7F : LEFT  8 px of each viewdata character
                (2 px margin | glyph cols  0-5)
  0x80-0xFF : RIGHT 8 px of the same characters
                (glyph cols 6-11 | 2 px gap)

This is used together with terminal_viewdata.c writing each logical column
as TWO physical columns (2*c → left half, 2*c+1 → right half with char|0x80),
rendered by the unmodified sw (8-px) TMDS renderer at 80 physical cols × 8 px
= 640 px — no ROW_ATTR_DBL_WIDTH needed.
"""

import sys
import os

BDF_FILE = os.path.join(os.path.dirname(__file__),
    '../../bedstead-3.261/bedstead-20.bdf')
OUT_FILE = os.path.join(os.path.dirname(__file__), '../src/font_viewdata.h')

CHAR_HEIGHT   = 20
CELL_WIDTH    = 12   # Bedstead DWIDTH
OUTPUT_WIDTH  = 12   # full glyph width; split into two 8-bit halves below
LEFT_MARGIN   = 2    # blank pixels to the left of the glyph in the 16-px cell
RIGHT_GAP     = 2    # blank pixels to the right (inter-character gap)
FONT_ASCENT   = 16   # from BDF FONT_ASCENT
FONT_DESCENT  = 4    # from BDF FONT_DESCENT
CHARS_PER_ROW = 32   # how many chars fit across 256-pixel-wide bitmap
NUM_CHARS     = 256

# Viewdata G0 character set: positions 0x20-0x7F
# Maps Viewdata slot -> Unicode codepoint to look up in Bedstead.
# Slots not listed here default to the same Unicode as the slot value (ASCII).
VIEWDATA_G0 = {}
for i in range(0x20, 0x80):
    VIEWDATA_G0[i] = i   # default: same as ASCII

# UK-specific Viewdata substitutions (per Prestel/SAA5050 spec)
VIEWDATA_G0[0x23] = 0x00A3   # £  pound sterling   (replaces #)
VIEWDATA_G0[0x24] = 0x0024   # $  dollar           (unchanged in Prestel)
VIEWDATA_G0[0x40] = 0x0040   # @  at               (unchanged)
VIEWDATA_G0[0x5B] = 0x2190   # ←  left arrow       (replaces [)
VIEWDATA_G0[0x5C] = 0x00BD   # ½  one half         (replaces \)
VIEWDATA_G0[0x5D] = 0x2192   # →  right arrow      (replaces ])
VIEWDATA_G0[0x5E] = 0x2191   # ↑  up arrow         (replaces ^)
VIEWDATA_G0[0x5F] = 0x0023   # #  hash/number      (replaces _)
VIEWDATA_G0[0x60] = 0x2014   # —  em dash / horizontal bar (replaces `)
VIEWDATA_G0[0x7B] = 0x00BC   # ¼  one quarter      (replaces {)
VIEWDATA_G0[0x7C] = 0x00A6   # ¦  broken bar       (replaces |)
VIEWDATA_G0[0x7D] = 0x00BE   # ¾  three quarters   (replaces })
VIEWDATA_G0[0x7E] = 0x00F7   # ÷  division sign    (replaces ~)
VIEWDATA_G0[0x7F] = 0x2588   # █  full block       (replaces DEL)


def parse_bdf(filename):
    """Parse BDF file. Returns (glyphs, font_ascent).
    glyphs: dict encoding -> (bbx_tuple, bitmap_int_list)
    bbx_tuple: (width, height, xoff, yoff)
    bitmap_int_list: list of ints, one per glyph row (MSB = leftmost pixel)
    """
    glyphs = {}
    current_encoding = None
    current_bbx = None
    current_bitmap = []
    in_bitmap = False
    font_ascent = FONT_ASCENT

    with open(filename, encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tokens = line.split()

            if tokens[0] == 'FONT_ASCENT':
                font_ascent = int(tokens[1])
            elif tokens[0] == 'ENCODING':
                current_encoding = int(tokens[1])
            elif tokens[0] == 'BBX':
                current_bbx = (int(tokens[1]), int(tokens[2]),
                               int(tokens[3]), int(tokens[4]))
            elif tokens[0] == 'BITMAP':
                in_bitmap = True
                current_bitmap = []
            elif tokens[0] == 'ENDCHAR':
                if current_encoding is not None and current_bbx is not None:
                    glyphs[current_encoding] = (current_bbx, current_bitmap[:])
                current_encoding = None
                current_bbx = None
                current_bitmap = []
                in_bitmap = False
            elif in_bitmap:
                current_bitmap.append(int(line, 16))

    return glyphs, font_ascent


def render_glyph(bbx, bitmap_rows, font_ascent=FONT_ASCENT,
                 char_height=CHAR_HEIGHT, cell_width=CELL_WIDTH,
                 output_width=OUTPUT_WIDTH):
    """
    Render one BDF glyph into the full cell_width × char_height pixel grid.

    Returns list of `char_height` integers, one per scanline.
    Each integer is `output_width` bits wide, MSB = leftmost pixel.
    For output_width=12: bit 11 = leftmost glyph column, bit 0 = rightmost.
    """
    w, h, xoff, yoff = bbx
    bytes_per_row = (w + 7) // 8

    # Build cell_width × char_height canvas (list of lists of 0/1)
    canvas = [[0] * cell_width for _ in range(char_height)]

    for r, row_val in enumerate(bitmap_rows):
        # r=0 is the topmost row of the glyph
        y = yoff + h - 1 - r          # y coordinate (0=baseline, positive=up)
        crow = font_ascent - 1 - y    # canvas row (0=top of cell)
        if crow < 0 or crow >= char_height:
            continue
        for b in range(w):
            bit_pos = (bytes_per_row * 8 - 1) - b
            pixel = (row_val >> bit_pos) & 1
            ccol = xoff + b
            if 0 <= ccol < cell_width:
                canvas[crow][ccol] = pixel

    # Pack all cell_width columns into a single integer per row (MSB = col 0)
    output = []
    for row in canvas:
        val = 0
        for i in range(output_width):
            if i < cell_width and row[i]:
                val |= (1 << (output_width - 1 - i))
        output.append(val)

    return output


def glyph_left_byte(row_12bit):
    """
    Left 8 px of the 16-px cell:
      screen pixels 0-1  = LEFT_MARGIN (0)
      screen pixels 2-7  = glyph cols 0-5

    Generator bit order (MSB=leftmost):
      bit7=0, bit6=0, bit5=g[0]..bit0=g[5]
    = row_12bit >> 6  (upper 6 bits of 12-bit row)
    """
    return (row_12bit >> 6) & 0xFF


def glyph_right_byte(row_12bit):
    """
    Right 8 px of the 16-px cell:
      screen pixels 8-13 = glyph cols 6-11
      screen pixels 14-15 = RIGHT_GAP (0)

    Generator bit order (MSB=leftmost):
      bit7=g[6]..bit2=g[11], bit1=0, bit0=0
    = (row_12bit & 0x3F) << 2
    """
    return ((row_12bit & 0x3F) << 2) & 0xFF


def make_blank_glyph(char_height=CHAR_HEIGHT):
    return [0] * char_height



def font_to_bmp_array(font):
    """
    Convert list of 256 glyph data (each CHAR_HEIGHT bytes) into a BMP-format
    byte array: bitmapWidth=256, bitmapHeight=160, stored bottom-to-top.

    Returns flat bytearray of 160 * 32 = 5120 bytes.
    """
    bmp = bytearray(160 * 32)
    for char_idx, glyph in enumerate(font):
        char_row = char_idx // CHARS_PER_ROW   # 0-7
        byte_col = char_idx  % CHARS_PER_ROW   # 0-31
        for scanline, byte_val in enumerate(glyph):
            # BMP row (bottom-to-top):
            br = 159 - char_row * CHAR_HEIGHT - scanline
            bmp[br * CHARS_PER_ROW + byte_col] = byte_val
    return bmp


def render_alpha_char(slot, glyphs, font_ascent):
    """
    Render the alpha character for slot (0x20-0x7F) using VIEWDATA_G0 mapping.
    Returns (rows_12bit, found:bool).
    """
    unicode_cp = VIEWDATA_G0[slot]
    if unicode_cp in glyphs:
        bbx, bmap = glyphs[unicode_cp]
        return render_glyph(bbx, bmap, font_ascent), True
    return None, False


def build_font(glyphs, font_ascent):
    """
    Build list of 256 glyph data arrays (one byte per scanline each).

    Slot layout:
      0x00-0x7F : LEFT  half (2 px margin + glyph cols 0-5)
      0x80-0xFF : RIGHT half (glyph cols 6-11 + 2 px gap)
    """
    font = []
    missing = []

    for slot in range(NUM_CHARS):
        if slot < 0x80:
            # Left half: alpha chars 0x20-0x7F
            if 0x20 <= slot <= 0x7F:
                rows_12bit, found = render_alpha_char(slot, glyphs, font_ascent)
                if found:
                    glyph_data = [glyph_left_byte(r) for r in rows_12bit]
                else:
                    glyph_data = make_blank_glyph()
                    unicode_cp = VIEWDATA_G0[slot]
                    missing.append(f'  0x{slot:02X} -> U+{unicode_cp:04X} not found')
            else:
                glyph_data = make_blank_glyph()
        else:
            # Right half: slot 0x80+k = right half of char k
            k = slot - 0x80
            if 0x20 <= k <= 0x7F:
                rows_12bit, found = render_alpha_char(k, glyphs, font_ascent)
                if found:
                    glyph_data = [glyph_right_byte(r) for r in rows_12bit]
                else:
                    glyph_data = make_blank_glyph()
            else:
                glyph_data = make_blank_glyph()

        font.append(glyph_data)

    return font, missing


def write_header(bmp_data, out_path, missing):
    header = """\
// -----------------------------------------------------------------------------
// font_viewdata.h — Viewdata/Prestel G0 alphanumeric font for VersaTerm
//
// Derived from the Bedstead font (public domain):
//   https://github.com/damianvila/bedstead
//
// Format : 256 chars × 20 scanlines, 8 pixels wide (1 byte per scanline).
// Bitmap : 256 × 160 pixels (32 chars/row × 8 char-rows), BMP bottom-to-top.
// charHeight  = 20
// bitmapWidth = 256, bitmapHeight = 160
//
// 16-px-native split (2 px margin + 12 px Bedstead glyph + 2 px gap):
//   Slots 0x00-0x7F : LEFT  8 px  (margin | glyph cols 0-5)
//   Slots 0x80-0xFF : RIGHT 8 px  (glyph cols 6-11 | gap)
//
// Generated by tools/bdf_to_viewdata.py — do not edit by hand.
// -----------------------------------------------------------------------------

static unsigned char __in_flash(".font") font_viewdata_bmp[] = {
"""
    hex_vals = [f'0x{b:02X}' for b in bmp_data]
    # 16 values per line
    lines = []
    for i in range(0, len(hex_vals), 16):
        lines.append('  ' + ', '.join(hex_vals[i:i+16]) + ',')
    header += '\n'.join(lines)
    header += '\n};\n'

    if missing:
        header += '\n/* Missing glyphs (shown as blank):\n'
        header += '\n'.join(missing)
        header += '\n*/\n'

    with open(out_path, 'w') as f:
        f.write(header)


def main():
    bdf_path = BDF_FILE
    out_path = OUT_FILE

    if len(sys.argv) > 1:
        bdf_path = sys.argv[1]
    if len(sys.argv) > 2:
        out_path = sys.argv[2]

    print(f'Parsing BDF: {bdf_path}')
    glyphs, font_ascent = parse_bdf(bdf_path)
    print(f'  {len(glyphs)} glyphs found, font_ascent={font_ascent}')

    print('Building font array ...')
    font, missing = build_font(glyphs, font_ascent)

    if missing:
        print(f'  WARNING: {len(missing)} missing glyphs (will render as blank):')
        for m in missing:
            print(m)

    bmp_data = font_to_bmp_array(font)
    print(f'  BMP data: {len(bmp_data)} bytes')

    print(f'Writing: {out_path}')
    write_header(bmp_data, out_path, missing)
    print('Done.')


if __name__ == '__main__':
    main()
