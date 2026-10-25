#ifndef NAND_FLASH_H
#define NAND_FLASH_H

#include <stdint.h>
#include <stdbool.h>
#include "config.h"

typedef struct {
    uint32_t channel;
    uint32_t package;
    uint32_t die;
    uint32_t plane;
    uint32_t block;
    uint32_t page;  // 내부에 logical page 번호를 포함할 수 있음
} PhysicalAddress;


#endif