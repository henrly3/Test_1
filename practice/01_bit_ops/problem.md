# 01. 비트 레지스터 조작

32비트 제어 레지스터를 다루는 함수들을 구현하세요. (`<stdint.h>`의 `uint32_t` 사용)

1. `uint32_t set_bit(uint32_t reg, int n)`: n번째 비트를 1로
2. `uint32_t clear_bit(uint32_t reg, int n)`: n번째 비트를 0으로
3. `uint32_t toggle_bit(uint32_t reg, int n)`: n번째 비트를 반전
4. `int count_ones(uint32_t x)`: 1인 비트의 개수 (내장 함수 `__builtin_popcount` 사용 금지)
5. `uint32_t write_field(uint32_t reg, int pos, int width, uint32_t value)`:
   `pos`부터 `width`비트 구간을 `value`로 덮어쓰기. 나머지 비트는 유지.
   `value`가 `width`비트보다 크면 넘치는 비트는 버림. (1 ≤ width ≤ 32)
6. `uint32_t reverse_bits(uint32_t x)`: 비트 순서를 뒤집기 (0번 ↔ 31번 …)
7. `int is_power_of_two(uint32_t x)`: 2의 거듭제곱이면 1, 아니면 0

## 예시

```
set_bit(0x00, 3)                     -> 0x08
clear_bit(0xFF, 0)                   -> 0xFE
count_ones(0xF0F0)                   -> 8
write_field(0xFFFFFFFF, 4, 4, 0x5)   -> 0xFFFFFF5F
reverse_bits(0x00000001)             -> 0x80000000
is_power_of_two(64)                  -> 1
is_power_of_two(0)                   -> 0
```

## 체크 포인트
- `1 << 31`은 `int`에서 정의되지 않은 동작(UB)입니다. `1u << n`처럼 부호 없는 상수를 쓰세요.
- `width == 32`일 때 `1u << 32`도 UB입니다. 마스크를 어떻게 만들지 생각해 보세요.
