/* quiz.md 정답 중 실행으로 확인 가능한 항목 검증 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

struct A { char c; int i; char d; };
struct B { int i; char c; char d; };

int main(void)
{
    /* Q1 */
    assert(sizeof(struct A) == 12);
    assert(sizeof(struct B) == 8);

    /* Q2 */
    int arr[5] = {1, 2, 3, 4, 5};
    int *p = (int *)(&arr + 1);
    assert(*(arr + 1) == 2 && *(p - 1) == 5);

    /* Q3: 의도적으로 signed/unsigned 비교 */
    unsigned int u = 1;
    int s = -1;
    assert(!((unsigned int)s < u));

    /* Q7: 리틀 엔디안 환경에서만 확인 */
    uint32_t x = 0x12345678;
    uint8_t *b = (uint8_t *)&x;
    if (b[0] == 0x78)
        assert(b[3] == 0x12);

    puts("07_c_quiz: OK");
    return 0;
}
