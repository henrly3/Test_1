#define _POSIX_C_SOURCE 200809L /* 테스트용 fmemopen/open_memstream */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef long long ll;

#define MAXT 100000

typedef struct {
    ll  arrive;
    int prio;
    ll  remain;
} Task;

static Task tasks[MAXT];
static int  order[MAXT];   /* 도착 순으로 정렬된 태스크 번호 */
static ll   done[MAXT];

/* ---------- 최소 힙 (태스크 번호를 저장) ---------- */

static int heap[MAXT];
static int heap_sz;

/* a 가 b 보다 먼저 실행되어야 하면 1: 우선순위 → 도착시각 → 번호 */
static int before(int a, int b)
{
    if (tasks[a].prio != tasks[b].prio)
        return tasks[a].prio < tasks[b].prio;
    if (tasks[a].arrive != tasks[b].arrive)
        return tasks[a].arrive < tasks[b].arrive;
    return a < b;
}

static void heap_swap(int i, int j)
{
    int t = heap[i];
    heap[i] = heap[j];
    heap[j] = t;
}

static void heap_push(int id)
{
    int i = heap_sz++;
    heap[i] = id;
    while (i > 0 && before(heap[i], heap[(i - 1) / 2])) {
        heap_swap(i, (i - 1) / 2);
        i = (i - 1) / 2;
    }
}

static void heap_pop(void)
{
    heap[0] = heap[--heap_sz];
    int i = 0;
    for (;;) {
        int l = 2 * i + 1, r = l + 1, best = i;
        if (l < heap_sz && before(heap[l], heap[best]))
            best = l;
        if (r < heap_sz && before(heap[r], heap[best]))
            best = r;
        if (best == i)
            break;
        heap_swap(i, best);
        i = best;
    }
}

/* ---------- 풀이 ---------- */

static int cmp_arrive(const void *pa, const void *pb)
{
    int a = *(const int *)pa, b = *(const int *)pb;
    if (tasks[a].arrive != tasks[b].arrive)
        return tasks[a].arrive < tasks[b].arrive ? -1 : 1;
    return a - b;
}

/* 실제 시험에서는 main 에서 solve(stdin, stdout) 호출 */
void solve(FILE *in, FILE *out)
{
    int n;
    if (fscanf(in, "%d", &n) != 1)
        return;
    for (int i = 0; i < n; i++) {
        if (fscanf(in, "%lld %d %lld", &tasks[i].arrive, &tasks[i].prio, &tasks[i].remain) != 3)
            return;
        order[i] = i;
    }
    qsort(order, n, sizeof order[0], cmp_arrive);

    heap_sz = 0;
    ll now = 0, switches = 0;
    int next = 0, last = -1, finished = 0;

    while (finished < n) {
        while (next < n && tasks[order[next]].arrive <= now)
            heap_push(order[next++]);

        if (heap_sz == 0) {
            now = tasks[order[next]].arrive;   /* idle: 다음 도착까지 점프 */
            continue;
        }

        int cur = heap[0];
        if (last != -1 && last != cur)
            switches++;
        last = cur;

        /* 현재 태스크 완료 시각과 다음 도착 시각 중 빠른 쪽까지 실행 */
        ll run_until = now + tasks[cur].remain;
        if (next < n && tasks[order[next]].arrive < run_until)
            run_until = tasks[order[next]].arrive;

        tasks[cur].remain -= run_until - now;
        now = run_until;
        if (tasks[cur].remain == 0) {
            heap_pop();
            done[cur] = now;
            finished++;
        }
        /* 남았으면 힙에 그대로 두고, 새로 도착한 태스크와 다시 비교 → 선점 */
    }

    for (int i = 0; i < n; i++)
        fprintf(out, "%lld\n", done[i]);
    fprintf(out, "%lld\n", switches);
}

/* ---- 테스트 ---- */

static void expect(const char *input, const char *want)
{
    FILE *in = fmemopen((void *)input, strlen(input), "r");
    char *got = NULL;
    size_t len = 0;
    FILE *out = open_memstream(&got, &len);
    solve(in, out);
    fclose(in);
    fclose(out);
    if (strcmp(got, want) != 0) {
        fprintf(stderr, "FAIL input:\n%s want:\n%s got:\n%s", input, want, got);
        exit(1);
    }
    free(got);
}

int main(void)
{
    expect("3\n0 5 4\n1 1 2\n2 3 1\n", "7\n3\n4\n3\n");      /* 문제 예시 */
    expect("1\n10 0 5\n", "15\n0\n");                         /* 늦게 도착 */
    expect("2\n0 1 2\n5 1 3\n", "2\n8\n1\n");                 /* idle 후 다른 태스크 */
    expect("2\n0 2 3\n1 2 1\n", "3\n4\n1\n");                 /* 같은 우선순위는 선점 안 함 */
    expect("2\n0 1 1\n0 1 1\n", "1\n2\n1\n");                 /* 동률이면 번호 순 */
    expect("3\n0 9 10\n2 1 1\n4 1 1\n", "12\n3\n5\n4\n");     /* 선점 후 복귀 반복 */
    expect("2\n1000000000 0 10000\n1000000000 1 10000\n",
           "1000010000\n1000020000\n1\n");                     /* 큰 시각 */

    puts("06_task_scheduler: OK");
    return 0;
}
