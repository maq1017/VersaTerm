#!/usr/bin/env python3
"""
Render Viewdata G0 alphanumeric characters from font_viewdata.h.

Reads the compiled hex array directly so you see exactly what is in the firmware.

Usage:
  python3 render_viewdata_font.py [h_file] [slot ...]

  h_file : path to font_viewdata.h  (default: ../src/font_viewdata.h)
  slot   : hex (0x41) or decimal (65) slot numbers  (default: all 0x20-0x7F)
"""

import os, sys, re

DEFAULT_H = os.path.join(os.path.dirname(__file__), '../src/font_viewdata.h')

CHAR_HEIGHT   = 20
CHARS_PER_ROW = 32
BMP_ROWS      = 160
BASELINE_ROW  = 15   # scanline index of baseline (font_ascent=16, 0-indexed)

VIEWDATA_G0_NAMES = {
    0x23: "£  (replaces #)",    0x5B: "←  (replaces [)",
    0x5C: "½  (replaces \\)",   0x5D: "→  (replaces ])",
    0x5E: "↑  (replaces ^)",    0x5F: "#  (replaces _)",
    0x60: "—  (replaces `)",    0x7B: "¼  (replaces {)",
    0x7C: "¦  (replaces |)",    0x7D: "¾  (replaces })",
    0x7E: "÷  (replaces ~)",    0x7F: "█  (replaces DEL)",
}


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
    """Return (min_line, max_line) in the .h file for all scanlines of a slot."""
    char_row = slot // CHARS_PER_ROW
    byte_col = slot  % CHARS_PER_ROW
    lines = []
    for s in range(CHAR_HEIGHT):
        br = (BMP_ROWS - 1) - char_row * CHAR_HEIGHT - s
        lines.append(data_start_line + (br * CHARS_PER_ROW + byte_col) // 16)
    return min(lines), max(lines)


def main():
    args = sys.argv[1:]

    h_path = DEFAULT_H
    if args and (args[0].endswith('.h') or os.sep in args[0] or args[0].startswith('.')):
        h_path = args.pop(0)

    slots = [int(a, 0) for a in args] if args else list(range(0x20, 0x80))

    if not os.path.exists(h_path):
        print(f"Error: file not found: {h_path}")
        sys.exit(1)

    bmp, data_start_line = parse_h_array(h_path)

    print()
    print("Viewdata G0 Alphanumeric Font")
    print("═" * 72)
    print("  Layout: ··margin··[glyph cols 0-5][glyph cols 6-11]··gap··")
    print("  A = baseline scanline   .h lines = font_viewdata.h")
    print()

    for slot in slots:
        if not (0x20 <= slot <= 0x7F):
            print(f"Slot 0x{slot:02X}: out of range (0x20-0x7F only)")
            continue

        left_slot  = slot
        right_slot = slot + 0x80

        char_repr = chr(slot) if 0x20 <= slot < 0x7F else ' '
        name = VIEWDATA_G0_NAMES.get(slot, f"'{char_repr}'")

        l_range = slot_h_line_range(left_slot,  data_start_line)
        r_range = slot_h_line_range(right_slot, data_start_line)

        print(f"Slot 0x{slot:02X} ({slot:3d})  {name}")
        print(f"  left=0x{left_slot:02X} (.h {l_range[0]}-{l_range[1]})  "
              f"right=0x{right_slot:02X} (.h {r_range[0]}-{r_range[1]})")

        left_bytes  = slot_scanlines(bmp, left_slot)
        right_bytes = slot_scanlines(bmp, right_slot)

        for row_i, (lb, rb) in enumerate(zip(left_bytes, right_bytes)):
            row = ''
            for bit in range(7, -1, -1):
                row += '█' if (lb >> bit) & 1 else '·'
            for bit in range(7, -1, -1):
                row += '█' if (rb >> bit) & 1 else '·'
            marker = 'A' if row_i == BASELINE_ROW else ' '
            print(f"  {row}  {marker}{row_i:2d}")
        print()


if __name__ == '__main__':
    main()
