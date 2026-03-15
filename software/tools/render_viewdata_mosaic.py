#!/usr/bin/env python3
"""
Render Viewdata mosaic patterns from font_viewdata_mosaic.h.

Reads the compiled hex array directly so you see exactly what is in the firmware.

Usage:
  python3 render_viewdata_mosaic.py [h_file] [pattern ...]

  h_file  : path to font_viewdata_mosaic.h  (default: ../src/font_viewdata_mosaic.h)
  pattern : pattern numbers 0-63  (default: all)
"""

import os, sys, re

DEFAULT_H = os.path.join(os.path.dirname(__file__), '../src/font_viewdata_mosaic.h')

CHAR_HEIGHT   = 20
CHARS_PER_ROW = 32
BMP_ROWS      = 160
HEADER_LINES  = 22   # lines before data in the .h file (data starts at line 23)

ROW_SPANS = [(0, 7), (7, 14), (14, 20)]


def parse_h_array(h_path):
    """Parse hex byte array from .h file. Returns (bytes_list, data_start_line)."""
    data_start_line = None
    all_bytes = []
    in_array = False
    with open(h_path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if not in_array:
                if '[]' in line and '=' in line and '{' in line:
                    in_array = True
                    data_start_line = lineno + 1
                continue
            if '};' in line:
                break
            all_bytes.extend(int(v, 16) for v in re.findall(r'0[xX][0-9A-Fa-f]+', line))
    return all_bytes, data_start_line


def slot_scanlines(bmp, slot):
    """Return list of CHAR_HEIGHT byte values for a slot, top scanline first."""
    char_row = slot // CHARS_PER_ROW
    byte_col = slot  % CHARS_PER_ROW
    return [bmp[(BMP_ROWS - 1 - char_row * CHAR_HEIGHT - s) * CHARS_PER_ROW + byte_col]
            for s in range(CHAR_HEIGHT)]


def slot_h_line_range(slot, data_start_line):
    char_row = slot // CHARS_PER_ROW
    byte_col = slot  % CHARS_PER_ROW
    lines = [data_start_line + ((BMP_ROWS - 1 - char_row * CHAR_HEIGHT - s) * CHARS_PER_ROW + byte_col) // 16
             for s in range(CHAR_HEIGHT)]
    return min(lines), max(lines)


def slot_for(pattern, side, separated):
    if side == 'left':
        base = 0x00 if not separated else 0x40
    else:
        base = 0x80 if not separated else 0xC0
    return base + pattern


def main():
    args = sys.argv[1:]

    h_path = DEFAULT_H
    if args and (args[0].endswith('.h') or os.sep in args[0] or args[0].startswith('.')):
        h_path = args.pop(0)

    patterns = [int(a) for a in args] if args else list(range(64))

    if not os.path.exists(h_path):
        print(f"Error: file not found: {h_path}")
        sys.exit(1)

    bmp, data_start_line = parse_h_array(h_path)

    print()
    print("Viewdata Mosaic Patterns")
    print("═" * 72)
    print("  Bits: TL=bit0  TR=bit1  ML=bit2  MR=bit3  BL=bit4  BR=bit5")
    print("  .h line ranges are for font_viewdata_mosaic.h")
    print()

    for p in patterns:
        if not (0 <= p <= 63):
            print(f"Pattern {p}: out of range (0-63 only)")
            continue

        tl = bool(p & 0x01); tr = bool(p & 0x02)
        ml = bool(p & 0x04); mr = bool(p & 0x08)
        bl = bool(p & 0x10); br = bool(p & 0x20)

        lc = slot_for(p, 'left',  False)
        ls = slot_for(p, 'left',  True)
        rc = slot_for(p, 'right', False)
        rs = slot_for(p, 'right', True)

        lc_r = slot_h_line_range(lc, data_start_line)
        ls_r = slot_h_line_range(ls, data_start_line)
        rc_r = slot_h_line_range(rc, data_start_line)
        rs_r = slot_h_line_range(rs, data_start_line)

        print(f"Pattern {p:2d}  (0b{p:06b})  "
              f"TL={int(tl)} TR={int(tr)} ML={int(ml)} MR={int(mr)} BL={int(bl)} BR={int(br)}")
        print(f"  Slots:  left-cont=0x{lc:02X} (.h {lc_r[0]}-{lc_r[1]})  "
              f"left-sep=0x{ls:02X} (.h {ls_r[0]}-{ls_r[1]})  "
              f"right-cont=0x{rc:02X} (.h {rc_r[0]}-{rc_r[1]})  "
              f"right-sep=0x{rs:02X} (.h {rs_r[0]}-{rs_r[1]})")

        lc_bytes = slot_scanlines(bmp, lc)
        ls_bytes = slot_scanlines(bmp, ls)
        rc_bytes = slot_scanlines(bmp, rc)
        rs_bytes = slot_scanlines(bmp, rs)

        print(f"  {'Contiguous (16px)':20s}  {'Separated (16px)':20s}")
        for row_i in range(CHAR_HEIGHT):
            lb, rb = lc_bytes[row_i], rc_bytes[row_i]
            lbs, rbs = ls_bytes[row_i], rs_bytes[row_i]
            cont = ''.join('█' if (lb>>b)&1 else '·' for b in range(7,-1,-1)) + \
                   ''.join('█' if (rb>>b)&1 else '·' for b in range(7,-1,-1))
            sep  = ''.join('█' if (lbs>>b)&1 else '·' for b in range(7,-1,-1)) + \
                   ''.join('█' if (rbs>>b)&1 else '·' for b in range(7,-1,-1))
            marker = {ROW_SPANS[0][0]:'T', ROW_SPANS[1][0]:'M', ROW_SPANS[2][0]:'B'}.get(row_i, ' ')
            print(f"  {cont}  {sep}  {marker}{row_i:2d}")
        print()


if __name__ == '__main__':
    main()
