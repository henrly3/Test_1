#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#define STX 0x02
#define ETX 0x03
#define MAX_SAMPLES 64

typedef struct {
    uint8_t id;
    int     count;
    int16_t samples[MAX_SAMPLES];
} Packet;

static uint16_t read_be16(const uint8_t *p)
{
    return (uint16_t)((p[0] << 8) | p[1]);
}

int parse_packet(const uint8_t *buf, int buf_len, Packet *out)
{
    if (buf_len < 6)
        return -1;
    if (buf[0] != STX)
        return -2;

    int len = read_be16(&buf[2]);
    if (4 + len + 2 > buf_len)
        return -1;
    if (buf[4 + len + 1] != ETX)
        return -2;
    if (len % 2 != 0 || len / 2 > MAX_SAMPLES)
        return -4;

    uint8_t chk = 0;
    for (int i = 1; i < 4 + len; i++)
        chk ^= buf[i];
    if (chk != buf[4 + len])
        return -3;

    out->id = buf[1];
    out->count = len / 2;
    for (int i = 0; i < out->count; i++)
        out->samples[i] = (int16_t)read_be16(&buf[4 + 2 * i]);
    return 0;
}

int main(void)
{
    Packet p;

    const uint8_t ok[] = {0x02, 0x07, 0x00, 0x04, 0x00, 0x64, 0xFF, 0x9C, 0x04, 0x03};
    assert(parse_packet(ok, sizeof ok, &p) == 0);
    assert(p.id == 7 && p.count == 2);
    assert(p.samples[0] == 100 && p.samples[1] == -100);

    const uint8_t empty[] = {0x02, 0x01, 0x00, 0x00, 0x01, 0x03};
    assert(parse_packet(empty, sizeof empty, &p) == 0 && p.count == 0);

    assert(parse_packet(ok, 5, &p) == -1);                     /* 잘림 */

    const uint8_t bad_stx[] = {0x05, 0x07, 0x00, 0x04, 0x00, 0x64, 0xFF, 0x9C, 0x04, 0x03};
    assert(parse_packet(bad_stx, sizeof bad_stx, &p) == -2);

    const uint8_t bad_chk[] = {0x02, 0x07, 0x00, 0x04, 0x00, 0x64, 0xFF, 0x9C, 0x00, 0x03};
    assert(parse_packet(bad_chk, sizeof bad_chk, &p) == -3);

    const uint8_t odd_len[] = {0x02, 0x07, 0x00, 0x01, 0xAA, 0xAC, 0x03};
    assert(parse_packet(odd_len, sizeof odd_len, &p) == -4);

    const uint8_t huge_len[] = {0x02, 0x07, 0xFF, 0xFF, 0x00, 0x03};
    assert(parse_packet(huge_len, sizeof huge_len, &p) == -1);

    puts("02_packet_parse: OK");
    return 0;
}
