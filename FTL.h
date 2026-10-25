#ifndef FTL_H
#define FTL_H

#include <stdint.h>
#include <stdbool.h>
#include "config.h"


typedef struct {
    bool is_programmed; // Indicates if the page has been programmed
    uint32_t LPN; // Logical page number corresponding to this physical page
} Entry;



//FTL mappings
void FTL_init(void);
void FTL_read(uint32_t lba, uint32_t *data);
void FTL_write(uint32_t lba, uint32_t *data);
void FTL_erase(uint32_t lba);





#endif