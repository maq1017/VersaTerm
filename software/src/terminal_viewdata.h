// -----------------------------------------------------------------------------
// terminal_viewdata.h — Prestel/Viewdata terminal emulator for VersaTerm
// -----------------------------------------------------------------------------

#ifndef TERMINAL_VIEWDATA_H
#define TERMINAL_VIEWDATA_H

#include <stdint.h>

void terminal_viewdata_init(void);
void terminal_viewdata_apply_settings(void);
void terminal_viewdata_receive_char(char c);
void terminal_viewdata_process_key(uint16_t key);

#endif // TERMINAL_VIEWDATA_H
