#define _POSIX_C_SOURCE 200809L /* 테스트용 fmemopen/open_memstream */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXN 1000
#define MAXM 1000

/* 큰 배열은 스택이 아니라 전역(static)에 둔다: 4MB 를 지역변수로 잡으면 스택 오버플로 */
static int g[MAXN][MAXM];
static int q[MAXN * MAXM];               /* BFS 큐: r * m + c 로 좌표를 한 정수에 담음 */
static int sizes[MAXN * MAXM / 2 + 1];   /* 군집 수 최대치: 체스판 배치일 때 약 N*M/2 */

static int cmp_desc(const void *a, const void *b)
{
    int x = *(const int *)a, y = *(const int *)b;
    return (x < y) - (x > y);            /* x - y 는 오버플로 가능성이 있어 피함 */
}

/* 실제 시험에서는 main 에서 solve(stdin, stdout) 호출 */
void solve(FILE *in, FILE *out)
{
    int n, m, t, k;
    if (fscanf(in, "%d %d %d %d", &n, &m, &t, &k) != 4)
        return;
    for (int r = 0; r < n; r++)
        for (int c = 0; c < m; c++)
            if (fscanf(in, "%d", &g[r][c]) != 1)
                return;

    static const int dr[] = {-1, 1, 0, 0};
    static const int dc[] = {0, 0, -1, 1};
    int cnt_targets = 0;

    for (int r = 0; r < n; r++) {
        for (int c = 0; c < m; c++) {
            if (g[r][c] < t)
                continue;
            int head = 0, tail = 0, cnt = 0;
            q[tail++] = r * m + c;
            g[r][c] = -1;                /* 방문 표시 (visited 배열 대신) */
            while (head < tail) {
                int cur = q[head++];
                int cr = cur / m, cc = cur % m;
                cnt++;
                for (int d = 0; d < 4; d++) {
                    int nr = cr + dr[d], nc = cc + dc[d];
                    if (nr < 0 || nr >= n || nc < 0 || nc >= m || g[nr][nc] < t)
                        continue;
                    g[nr][nc] = -1;
                    q[tail++] = nr * m + nc;
                }
            }
            if (cnt >= k)
                sizes[cnt_targets++] = cnt;
        }
    }

    qsort(sizes, cnt_targets, sizeof sizes[0], cmp_desc);
    fprintf(out, "%d\n", cnt_targets);
    for (int i = 0; i < cnt_targets; i++)
        fprintf(out, "%d%c", sizes[i], i + 1 < cnt_targets ? ' ' : '\n');
}

/* ---- 테스트 ---- */

static char *run(const char *input)
{
    FILE *in = fmemopen((void *)input, strlen(input), "r");
    char *buf = NULL;
    size_t len = 0;
    FILE *out = open_memstream(&buf, &len);
    solve(in, out);
    fclose(in);
    fclose(out);
    return buf;
}

static void expect(const char *input, const char *want)
{
    char *got = run(input);
    if (strcmp(got, want) != 0) {
        fprintf(stderr, "FAIL\n want: %s got: %s", want, got);
        exit(1);
    }
    free(got);
}

int main(void)
{
    expect("5 6 100 2\n"
           "120 130   0   0   0 200\n"
           "  0 110   0  90   0 210\n"
           "  0   0   0 150   0   0\n"
           " 99   0 101 160 170   0\n"
           "  0   0   0   0   0 255\n",
           "3\n4 3 2\n");
    expect("2 2 10 1\n0 0\n0 0\n", "0\n");                     /* 표적 없음 */
    expect("3 3 1 2\n1 0 1\n0 1 0\n1 0 1\n", "0\n");           /* 전부 잡음 */
    expect("2 2 1 1\n1 0\n0 1\n", "2\n1 1\n");                 /* 대각선은 연결 아님 */
    expect("2 3 0 1\n0 0 0\n0 0 0\n", "1\n6\n");               /* T=0 */

    /* 1000x1000 전부 탐지: 재귀 DFS 였다면 깊이 100만 → 스택 오버플로 */
    {
        char *big = NULL;
        size_t len = 0;
        FILE *f = open_memstream(&big, &len);
        fputs("1000 1000 1 1\n", f);
        for (int i = 0; i < MAXN; i++) {
            for (int j = 0; j < MAXM; j++)
                fputs("1 ", f);
            fputc('\n', f);
        }
        fclose(f);
        expect(big, "1\n1000000\n");
        free(big);
    }

    puts("05_radar_grid: OK");
    return 0;
}
