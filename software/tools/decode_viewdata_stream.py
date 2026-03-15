#!/usr/bin/env python3
"""
Decode a captured Viewdata/Prestel serial stream and show what each screen
row renders — including which font slots are used — so you can cross-reference
with font_viewdata.h and font_viewdata_mosaic.h for manual editing.

Usage:
  python3 decode_viewdata_stream.py <stream_file> [row ...]

  stream_file : tcpdump hex dump or raw binary of the Viewdata stream
  row         : optional row numbers to show detail for (default: all)

Output for each row:
  - The raw logical content (decoded printable + control codes)
  - A rendered visual line showing the 16-px composite glyphs
  - Font slot numbers (hex) for each character position
"""

import os, sys, re

VD_COLS = 40
VD_ROWS = 24

# C1 control code names
C1_NAMES = {
    0x40: 'αBlk', 0x41: 'αRed', 0x42: 'αGrn', 0x43: 'αYel',
    0x44: 'αBlu', 0x45: 'αMag', 0x46: 'αCyn', 0x47: 'αWht',
    0x48: 'Flsh', 0x49: 'Stdy', 0x4A: 'EndB', 0x4B: 'StaB',
    0x4C: 'Nrml', 0x4D: 'DblH', 0x4E: 'S1  ', 0x4F: 'S2  ',
    0x50: 'mBlk', 0x51: 'mRed', 0x52: 'mGrn', 0x53: 'mYel',
    0x54: 'mBlu', 0x55: 'mMag', 0x56: 'mCyn', 0x57: 'mWht',
    0x58: 'Conc', 0x59: 'Cont', 0x5A: 'Sep ', 0x5B: '--- ',
    0x5C: 'BkBg', 0x5D: 'NewB', 0x5E: 'Hold', 0x5F: 'Rels',
}

COLOUR_NAMES = {0:'Blk',9:'Red',10:'Grn',11:'Yel',12:'Blu',13:'Mag',14:'Cyn',15:'Wht'}

VIEWDATA_G0_NAMES = {
    0x23:'£', 0x5B:'←', 0x5C:'½', 0x5D:'→', 0x5E:'↑', 0x5F:'#',
    0x60:'—', 0x7B:'¼', 0x7C:'¦', 0x7D:'¾', 0x7E:'÷', 0x7F:'█',
}

VD_COLOUR_TABLE = [0, 9, 10, 11, 12, 13, 14, 15]  # index 0-7 → framebuf colour

# --------------------------------------------------------------------------
# Parse the dump file (handles tcpdump hex format or raw hex lines)
# --------------------------------------------------------------------------
def parse_stream(path):
    """Extract raw bytes from a tcpdump-style hex dump or plain hex file."""
    bytes_out = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            # Skip header lines (start with '<', '#', or are empty)
            if not line or line.startswith('<') or line.startswith('#'):
                continue
            # tcpdump format: "XX XX XX XX  XX XX ... ascii"
            # Extract all hex tokens from the left side (before any ASCII column)
            # Match 2-char hex tokens
            tokens = re.findall(r'\b([0-9a-fA-F]{2})\b', line.split('  ')[0])
            if not tokens:
                # Try whole line (plain hex list)
                tokens = re.findall(r'[0-9a-fA-F]{2}', line)
            bytes_out.extend(int(t, 16) for t in tokens)
    return bytes(bytes_out)


# --------------------------------------------------------------------------
# Mosaic slot lookup (mirrors vd_mosaic_slot in terminal_viewdata.c)
# --------------------------------------------------------------------------
def mosaic_slot(c, separated):
    if   0x20 <= c <= 0x3F: pattern = c - 0x20
    elif 0x60 <= c <= 0x7F: pattern = c - 0x40
    else: return None  # blast-through
    return pattern + (0x40 if separated else 0x00)


# --------------------------------------------------------------------------
# Simulate the Viewdata terminal
# --------------------------------------------------------------------------
def simulate(stream):
    """
    Simulate the Viewdata terminal.
    Returns vd_buf[row][col] and vd_ctrl[row][col] as 2D lists.
    """
    vd_buf  = [[0x20]*VD_COLS for _ in range(VD_ROWS)]
    vd_ctrl = [[0x00]*VD_COLS for _ in range(VD_ROWS)]
    col, row, esc = 0, 0, False

    def put(raw, ctrl):
        nonlocal col, row
        if row < VD_ROWS and col < VD_COLS:
            vd_buf [row][col] = raw
            vd_ctrl[row][col] = ctrl
        col += 1
        if col >= VD_COLS:
            col = 0; row += 1
            if row >= VD_ROWS: row = VD_ROWS - 1

    for b in stream:
        c = b & 0x7F
        if esc:
            esc = False
            if 0x40 <= c <= 0x5F:
                put(0x20, c)
            continue
        if   c == 0x00: pass
        elif c == 0x08: col = max(0, col-1)
        elif c == 0x09: col = min(VD_COLS-1, col+1)
        elif c == 0x0A: row = min(VD_ROWS-1, row+1)
        elif c == 0x0B: row = max(0, row-1)
        elif c == 0x0C:
            vd_buf  = [[0x20]*VD_COLS for _ in range(VD_ROWS)]
            vd_ctrl = [[0x00]*VD_COLS for _ in range(VD_ROWS)]
            col = row = 0
        elif c == 0x0D: col = 0
        elif c == 0x1B: esc = True
        elif c == 0x1E: col = 0; row = 0
        elif 0x80 <= c <= 0x9F: put(0x20, c - 0x40)
        elif c >= 0x20: put(c, 0x00)

    return vd_buf, vd_ctrl


# --------------------------------------------------------------------------
# Decode one row into rendered cells
# --------------------------------------------------------------------------
def decode_row(vd_buf_row, vd_ctrl_row):
    """
    Replay the attribute state machine for one row.
    Returns list of dicts, one per column:
      { raw, ctrl, display_char, is_mosaic, slot, fg, bg, separated, double_height }
    """
    fg, bg = 15, 0   # white on black
    graphics = False
    flash = False
    conceal = False
    separated = False
    double_height = False
    hold_graphics = False
    held_slot = 0x00
    held_slot_valid = False

    cells = []
    for col in range(VD_COLS):
        raw  = vd_buf_row[col]
        ctrl = vd_ctrl_row[col]

        if ctrl:
            fg_before = fg; bg_before = bg
            flash_before = flash; conceal_before = conceal

            if ctrl == 0x40:
                graphics = False; conceal = False
                held_slot = 0; held_slot_valid = False
            elif 0x41 <= ctrl <= 0x47:
                fg = VD_COLOUR_TABLE[ctrl - 0x40]; graphics = False; conceal = False
                held_slot = 0; held_slot_valid = False
            elif 0x50 <= ctrl <= 0x57:
                fg = VD_COLOUR_TABLE[ctrl - 0x50]; graphics = True; conceal = False
                if not hold_graphics: held_slot = 0; held_slot_valid = False
            elif ctrl == 0x48: flash = True
            elif ctrl == 0x49: flash = False
            elif ctrl == 0x4C: double_height = False; held_slot = 0; held_slot_valid = False
            elif ctrl == 0x4D: double_height = True;  held_slot = 0; held_slot_valid = False
            elif ctrl == 0x58: conceal = True
            elif ctrl == 0x59: separated = False
            elif ctrl == 0x5A: separated = True
            elif ctrl == 0x5C: bg = 0
            elif ctrl == 0x5D: bg = fg
            elif ctrl == 0x5E: hold_graphics = True
            elif ctrl == 0x5F: hold_graphics = False

            display_hold = hold_graphics if ctrl == 0x5E else (hold_graphics if ctrl != 0x5F else False)
            if display_hold and graphics and held_slot_valid:
                display_char = held_slot; is_mosaic = True; slot = held_slot
            else:
                display_char = 0x20; is_mosaic = False; slot = None

            cell_bg = bg if ctrl in (0x5C, 0x5D) else bg_before
            cell_fg = bg_before if conceal_before else fg_before

        else:
            if graphics:
                s = mosaic_slot(raw, separated)
                if s is None:
                    display_char = raw; is_mosaic = False; slot = None
                else:
                    display_char = s; is_mosaic = True; slot = s
                    held_slot = s; held_slot_valid = True
            else:
                display_char = raw; is_mosaic = False; slot = None
            cell_fg = bg if conceal else fg
            cell_bg = bg

        cells.append({
            'raw': raw, 'ctrl': ctrl,
            'display_char': display_char,
            'is_mosaic': is_mosaic,
            'slot': slot,           # mosaic left-half slot (or None)
            'fg': cell_fg, 'bg': cell_bg,
            'separated': separated,
            'double_height': double_height,
        })
    return cells


# --------------------------------------------------------------------------
# Render a decoded row visually (just characters, no colour)
# --------------------------------------------------------------------------
def render_row_text(cells):
    """Return a string showing what each cell displays (ASCII-art level)."""
    out = ''
    for c in cells:
        if c['ctrl']:
            out += '·'   # control cell (space / held glyph not shown here)
        elif c['is_mosaic']:
            # Show mosaic pattern as a mini indicator
            p = c['slot'] & 0x3F  # pattern 0-63
            out += f'[{p:02X}]'
        else:
            ch = c['display_char']
            char = VIEWDATA_G0_NAMES.get(ch, chr(ch) if 0x20 <= ch < 0x7F else '?')
            out += char
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <stream_file> [row ...]")
        sys.exit(1)

    stream_path = sys.argv[1]
    filter_rows = [int(a) for a in sys.argv[2:]] if len(sys.argv) > 2 else None

    stream = parse_stream(stream_path)
    print(f"Stream: {len(stream)} bytes from {stream_path}")

    vd_buf, vd_ctrl = simulate(stream)

    print()
    print("Decoded screen content")
    print("═" * 72)
    print("  Ctrl cells shown as ·   Mosaic cells shown as [pattern-hex]")
    print("  is_mosaic=True → uses font_viewdata_mosaic.h  (slot shown)")
    print("  is_mosaic=False → uses font_viewdata.h         (char code shown)")
    print()

    for row in range(VD_ROWS):
        if filter_rows and row not in filter_rows:
            continue

        cells = decode_row(vd_buf[row], vd_ctrl[row])

        # Summarise unique mosaic slots and alpha chars used
        mosaic_slots = sorted(set(c['slot'] for c in cells
                                  if c['is_mosaic'] and c['slot'] is not None))
        alpha_chars  = sorted(set(c['display_char'] for c in cells
                                  if not c['ctrl'] and not c['is_mosaic']
                                  and c['display_char'] != 0x20))
        has_dbl = any(c['double_height'] for c in cells)

        print(f"Row {row:2d} {'[DOUBLE HEIGHT]' if has_dbl else ''}:")
        print(f"  {render_row_text(cells)}")

        if mosaic_slots:
            print(f"  Mosaic slots (font_viewdata_mosaic.h):")
            for s in mosaic_slots:
                sep_flag = ' (separated)' if s >= 0x40 else ' (contiguous)'
                pattern  = s & 0x3F
                tl = bool(pattern&0x01); tr = bool(pattern&0x02)
                ml = bool(pattern&0x04); mr = bool(pattern&0x08)
                bl = bool(pattern&0x10); br = bool(pattern&0x20)
                print(f"    left=0x{s:02X} right=0x{s|0x80:02X}{sep_flag}  "
                      f"pattern={pattern:2d} TL={int(tl)} TR={int(tr)} "
                      f"ML={int(ml)} MR={int(mr)} BL={int(bl)} BR={int(br)}")

        if alpha_chars:
            print(f"  Alpha chars (font_viewdata.h):")
            for c in alpha_chars:
                name = VIEWDATA_G0_NAMES.get(c, chr(c) if 0x20 <= c < 0x7F else f'0x{c:02X}')
                print(f"    slot=0x{c:02X} right=0x{c|0x80:02X}  '{name}'")

        print()


if __name__ == '__main__':
    main()
