# 03. UART 링 버퍼

UART 수신 인터럽트에서 받은 바이트를 저장하고, 메인 루프에서 꺼내 쓰는
고정 크기 링 버퍼(원형 큐)를 **동적 할당 없이** 구현하세요.

```c
#define RB_SIZE 8   /* 실제로 저장 가능한 최대 바이트 수 */

typedef struct { ... } RingBuf;

void rb_init(RingBuf *rb);
int  rb_push(RingBuf *rb, uint8_t data);  /* 성공 1, 꽉 차면 0 (데이터 버림) */
int  rb_pop(RingBuf *rb, uint8_t *data);  /* 성공 1, 비어 있으면 0 */
int  rb_count(const RingBuf *rb);         /* 현재 저장된 바이트 수 */
int  rb_peek_all(const RingBuf *rb, uint8_t *dst); /* 꺼내지 않고 순서대로 복사, 개수 반환 */
```

## 예시

```
push 1..8  -> 모두 성공, count = 8
push 9     -> 0 (꽉 참)
pop x3     -> 1, 2, 3
push 9,10,11 -> 성공 (인덱스가 한 바퀴 돎)
peek_all   -> 4 5 6 7 8 9 10 11
```

## 체크 포인트
- **full과 empty 구분**: `head == tail`이 두 경우를 모두 뜻하지 않게 하려면
  (a) `count` 변수를 두거나 (b) 한 칸을 비워 두는 방법이 있습니다. 차이점을 설명할 수 있어야 합니다.
- 크기가 2의 거듭제곱이면 `% SIZE` 대신 `& (SIZE - 1)`로 빠르게 계산할 수 있습니다.
- (면접 대비) ISR과 메인 루프가 함께 쓸 때 `volatile`이 필요한 이유, 그리고
  producer가 head만, consumer가 tail만 고치면 단일 생산자/소비자 환경에서 락 없이 안전한 이유.
