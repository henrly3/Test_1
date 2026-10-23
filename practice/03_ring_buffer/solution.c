#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#define RB_SIZE 8
/* 한 칸을 비워 full/empty 를 구분하므로 내부 배열은 +1, 2의 거듭제곱 마스크 대신 % 사용 */
#define RB_CAP  (RB_SIZE + 1)

typedef struct {
    uint8_t buf[RB_CAP];
    volatile uint16_t head; /* 다음에 쓸 위치 (producer: ISR) */
    volatile uint16_t tail; /* 다음에 읽을 위치 (consumer: main) */
} RingBuf;

void rb_init(RingBuf *rb) { rb->head = rb->tail = 0; }

int rb_count(const RingBuf *rb)
{
    return (rb->head + RB_CAP - rb->tail) % RB_CAP;
}

int rb_push(RingBuf *rb, uint8_t data)
{
    uint16_t next = (rb->head + 1) % RB_CAP;
    if (next == rb->tail)
        return 0; /* full */
    rb->buf[rb->head] = data;
    rb->head = next; /* 데이터 기록 후 인덱스 갱신 */
    return 1;
}

int rb_pop(RingBuf *rb, uint8_t *data)
{
    if (rb->head == rb->tail)
        return 0; /* empty */
    *data = rb->buf[rb->tail];
    rb->tail = (rb->tail + 1) % RB_CAP;
    return 1;
}

int rb_peek_all(const RingBuf *rb, uint8_t *dst)
{
    int n = 0;
    for (uint16_t i = rb->tail; i != rb->head; i = (i + 1) % RB_CAP)
        dst[n++] = rb->buf[i];
    return n;
}

int main(void)
{
    RingBuf rb;
    uint8_t v, out[RB_SIZE];

    rb_init(&rb);
    assert(rb_count(&rb) == 0);
    assert(rb_pop(&rb, &v) == 0);

    for (int i = 1; i <= 8; i++)
        assert(rb_push(&rb, (uint8_t)i) == 1);
    assert(rb_count(&rb) == 8);
    assert(rb_push(&rb, 9) == 0);

    for (int i = 1; i <= 3; i++) {
        assert(rb_pop(&rb, &v) == 1);
        assert(v == i);
    }
    for (int i = 9; i <= 11; i++)
        assert(rb_push(&rb, (uint8_t)i) == 1);
    assert(rb_push(&rb, 12) == 0);

    int n = rb_peek_all(&rb, out);
    assert(n == 8);
    for (int i = 0; i < n; i++)
        assert(out[i] == 4 + i);

    while (rb_pop(&rb, &v))
        ;
    assert(rb_count(&rb) == 0);

    puts("03_ring_buffer: OK");
    return 0;
}
