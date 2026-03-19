// -----------------------------------------------------------------------------
// terminal_mode7.h — BBC Micro Mode 7 terminal emulator for VersaTerm
// -----------------------------------------------------------------------------

#ifndef TERMINAL_MODE7_H
#define TERMINAL_MODE7_H

#include <stdint.h>

void terminal_mode7_init(void);
void terminal_mode7_apply_settings(void);
void terminal_mode7_receive_char(char c);
void terminal_mode7_process_key(uint16_t key);

#endif // TERMINAL_MODE7_H
