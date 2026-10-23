#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static int is_space(char c) { return c == ' ' || c == '\t'; }

int my_atoi(const char *s, int32_t *out)
{
    if (s == NULL)
        return 0;

    while (is_space(*s))
        s++;

    int neg = 0;
    if (*s == '+' || *s == '-') {
        neg = (*s == '-');
        s++;
    }

    /* 음수 방향으로 누적하면 INT32_MIN 까지 넘치지 않고 표현 가능 */
    int32_t val = 0;
    int digits = 0;
    while (*s >= '0' && *s <= '9') {
        int d = *s - '0';
        if (val < (INT32_MIN + d) / 10)
            return 0;
        int32_t next = val * 10;
        if (next < INT32_MIN + d)
            return 0;
        val = next - d;
        digits++;
        s++;
    }
    if (digits == 0)
        return 0;

    while (is_space(*s))
        s++;
    if (*s != '\0')
        return 0;

    if (!neg) {
        if (val == INT32_MIN)
            return 0; /* +2147483648 */
        val = -val;
    }
    *out = val;
    return 1;
}

int main(void)
{
    int32_t v;

    assert(my_atoi("42", &v) && v == 42);
    assert(my_atoi("   -17  ", &v) && v == -17);
    assert(my_atoi("\t+0", &v) && v == 0);
    assert(my_atoi("007", &v) && v == 7);
    assert(my_atoi("2147483647", &v) && v == INT32_MAX);
    assert(my_atoi("-2147483648", &v) && v == INT32_MIN);
    assert(!my_atoi("2147483648", &v));
    assert(!my_atoi("-2147483649", &v));
    assert(!my_atoi("99999999999", &v));
    assert(!my_atoi("12a", &v));
    assert(!my_atoi("1 2", &v));
    assert(!my_atoi("-", &v));
    assert(!my_atoi("", &v));
    assert(!my_atoi("+-3", &v));
    assert(!my_atoi(NULL, &v));

    puts("04_my_atoi: OK");
    return 0;
}
