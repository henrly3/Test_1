#include <assert.h>
#include <stdint.h>
#include <stdio.h>

uint32_t set_bit(uint32_t reg, int n)    { return reg | (1u << n); }
uint32_t clear_bit(uint32_t reg, int n)  { return reg & ~(1u << n); }
uint32_t toggle_bit(uint32_t reg, int n) { return reg ^ (1u << n); }

/* Brian Kernighan: x & (x-1) 은 가장 낮은 1비트를 지운다 */
int count_ones(uint32_t x)
{
    int cnt = 0;
    while (x) {
        x &= x - 1;
        cnt++;
    }
    return cnt;
}

uint32_t write_field(uint32_t reg, int pos, int width, uint32_t value)
{
    /* width == 32 이면 1u << 32 는 UB 이므로 따로 처리 */
    uint32_t mask = (width >= 32) ? 0xFFFFFFFFu : ((1u << width) - 1u);
    reg &= ~(mask << pos);
    reg |= (value & mask) << pos;
    return reg;
}

uint32_t reverse_bits(uint32_t x)
{
    uint32_t r = 0;
    for (int i = 0; i < 32; i++) {
        r = (r << 1) | (x & 1u);
        x >>= 1;
    }
    return r;
}

int is_power_of_two(uint32_t x) { return x != 0 && (x & (x - 1)) == 0; }

int main(void)
{
    assert(set_bit(0x00, 3) == 0x08);
    assert(set_bit(0x00, 31) == 0x80000000u);
    assert(clear_bit(0xFF, 0) == 0xFE);
    assert(toggle_bit(0x0F, 4) == 0x1F);
    assert(toggle_bit(0x1F, 4) == 0x0F);
    assert(count_ones(0xF0F0) == 8);
    assert(count_ones(0) == 0);
    assert(count_ones(0xFFFFFFFFu) == 32);
    assert(write_field(0xFFFFFFFFu, 4, 4, 0x5) == 0xFFFFFF5Fu);
    assert(write_field(0x00000000u, 0, 3, 0xFF) == 0x7);   /* 넘치는 비트 버림 */
    assert(write_field(0x12345678u, 0, 32, 0xCAFEBABEu) == 0xCAFEBABEu);
    assert(reverse_bits(0x00000001u) == 0x80000000u);
    assert(reverse_bits(0x0000000Fu) == 0xF0000000u);
    assert(is_power_of_two(64) == 1);
    assert(is_power_of_two(0) == 0);
    assert(is_power_of_two(96) == 0);
    puts("01_bit_ops: OK");
    return 0;
}
