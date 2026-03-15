#!/usr/bin/env python3
"""
Render all 64 Viewdata mosaic patterns visually in the terminal.

For each pattern (0-63), shows:
  - Pattern number and 6-bit breakdown (TL TR ML MR BL BR)
  - ASCII rendering of the 8×20 pixel glyph (contiguous and separated modes)
  - The 4 character slot indices in font_viewdata_mosaic.h
  - The .h file line numbers where each slot's scanlines live

BMP layout (bottom-to-top, 32 bytes/row, 160 rows):
  char at slot c  → char_row = c // 32, byte_col = c % 32
  scanline s (0=top) → BMP row br = 159 - char_row*20 - s
                     → BMP offset = br*32 + byte_col
  .h file line = 23 + BMP_offset // 16   (data starts at .h line 23)
"""

import os
import sys

CHAR_HEIGHT   = 20
CHARS_PER_ROW = 32
BMP_ROWS      = 160   # 8 char-rows × 20 scanlines
HEADER_LINES  = 22    # lines before data in the .h file (data starts at line 23)

ROW_SPANS = [
    (0,  7),   # top    block
    (7,  14),  # middle block
    (14, 20),  # bottom block
]

LEFT_CONT = 0xFF
LEFT_SEP  = 0x7E


def make_half_glyph(pattern, side, separated=False):
    """Return list of CHAR_HEIGHT bytes for the LEFT or RIGHT half of pattern."""
    if side == 'left':
        on_bits = [bool(pattern & 0x01), bool(pattern & 0x04), bool(pattern & 0x10)]
    else:
        on_bits = [bool(pattern & 0x02), bool(pattern & 0x08), bool(pattern & 0x20)]
    fill = LEFT_SEP if separated else LEFT_CONT
    rows = []
    for row_idx, (rs, re) in enumerate(ROW_SPANS):
        rows.extend([fill if on_bits[row_idx] else 0] * (re - rs))
    return rows


def make_glyph(pattern, separated=False):
    """Return list of CHAR_HEIGHT bytes for the LEFT half of pattern (back-compat)."""
    return make_half_glyph(pattern, 'left', separated)


def composite_lines(pattern, separated=False):
    """Render the full 16-px cell (left half | right half) as ASCII lines."""
    left  = make_half_glyph(pattern, 'left',  separated)
    right = make_half_glyph(pattern, 'right', separated)
    lines = []
    for lbyte, rbyte in zip(left, right):
        row = ''
        for bit in range(7, -1, -1):
            row += '█' if (lbyte >> bit) & 1 else '·'
        for bit in range(7, -1, -1):
            row += '█' if (rbyte >> bit) & 1 else '·'
        lines.append(row)
    return lines


def glyph_to_lines(glyph, scale_x=2):
    """Render glyph bytes as ASCII lines. Each pixel → scale_x chars."""
    lines = []
    for byte_val in glyph:
        row = ''
        for bit in range(7, -1, -1):
            px = '█' if (byte_val >> bit) & 1 else '·'
            row += px * scale_x
        lines.append(row)
    return lines


def bmp_line_for_slot(slot, scanline):
    """Return the .h file line number (1-based) for a given slot and scanline."""
    char_row = slot // CHARS_PER_ROW
    byte_col = slot  % CHARS_PER_ROW
    br       = (BMP_ROWS - 1) - char_row * CHAR_HEIGHT - scanline
    offset   = br * CHARS_PER_ROW + byte_col
    return HEADER_LINES + 1 + offset // 16


def slot_line_range(slot):
    """Return (first_h_line, last_h_line) for the 20 scanlines of a slot."""
    lines = [bmp_line_for_slot(slot, s) for s in range(CHAR_HEIGHT)]
    return min(lines), max(lines)


def render_pattern(pattern, side='left', separated=False):
    """
    Build a list of display lines for one pattern/mode.
    side: 'left' uses bits 0,2,4; 'right' uses bits 1,3,5 (mirrored in the font).
    We always render the LEFT-half glyph shape (both halves are symmetric).
    """
    return make_glyph(pattern, separated)


def slot_for(pattern, side, separated):
    if side == 'left':
        base = 0x00 if not separated else 0x40
    else:
        base = 0x80 if not separated else 0xC0
    return base + pattern


def main():
    # Optional: filter to specific pattern numbers
    if len(sys.argv) > 1:
        try:
            patterns = [int(a) for a in sys.argv[1:]]
        except ValueError:
            print(f"Usage: {sys.argv[0]} [pattern_number ...]")
            sys.exit(1)
    else:
        patterns = list(range(64))

    print()
    print("Viewdata Mosaic Patterns")
    print("═" * 72)
    print("  Bits: TL=bit0  TR=bit1  ML=bit2  MR=bit3  BL=bit4  BR=bit5")
    print("  Left half glyph shown (right half is the mirror image)")
    print("  .h line ranges are for font_viewdata_mosaic.h")
    print()

    for p in patterns:
        tl = bool(p & 0x01)
        tr = bool(p & 0x02)
        ml = bool(p & 0x04)
        mr = bool(p & 0x08)
        bl = bool(p & 0x10)
        br = bool(p & 0x20)

        # Slots
        lc_slot = slot_for(p, 'left',  False)  # left  contiguous
        ls_slot = slot_for(p, 'left',  True)   # left  separated
        rc_slot = slot_for(p, 'right', False)  # right contiguous
        rs_slot = slot_for(p, 'right', True)   # right separated

        lc_lines = slot_line_range(lc_slot)
        ls_lines = slot_line_range(ls_slot)
        rc_lines = slot_line_range(rc_slot)
        rs_lines = slot_line_range(rs_slot)

        print(f"Pattern {p:2d}  (0b{p:06b})  "
              f"TL={int(tl)} TR={int(tr)} ML={int(ml)} MR={int(mr)} BL={int(bl)} BR={int(br)}")
        print(f"  Slots:  left-cont=0x{lc_slot:02X} (.h {lc_lines[0]}-{lc_lines[1]})  "
              f"left-sep=0x{ls_slot:02X} (.h {ls_lines[0]}-{ls_lines[1]})  "
              f"right-cont=0x{rc_slot:02X} (.h {rc_lines[0]}-{rc_lines[1]})  "
              f"right-sep=0x{rs_slot:02X} (.h {rs_lines[0]}-{rs_lines[1]})")

        # Render contiguous and separated full 16-px cells side by side
        cont_lines = composite_lines(p, separated=False)
        sep_lines  = composite_lines(p, separated=True)

        print(f"  {'Contiguous (16px)':20s}  {'Separated (16px)':20s}")
        for row_i, (cl, sl) in enumerate(zip(cont_lines, sep_lines)):
            marker = ' '
            if row_i == ROW_SPANS[0][0]: marker = 'T'
            elif row_i == ROW_SPANS[1][0]: marker = 'M'
            elif row_i == ROW_SPANS[2][0]: marker = 'B'
            print(f"  {cl}  {sl}  {marker}{row_i:2d}")
        print()


if __name__ == '__main__':
    main()
