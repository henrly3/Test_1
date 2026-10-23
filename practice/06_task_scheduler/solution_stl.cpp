#include <algorithm>
#include <cassert>
#include <iostream>
#include <queue>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

using namespace std;
using ll = long long;

struct Task {
    ll arrive;
    int prio;
    ll remain;
};

string solve(istream &in)
{
    int n;
    in >> n;
    vector<Task> tasks(n);
    for (auto &t : tasks)
        in >> t.arrive >> t.prio >> t.remain;

    // 도착 순으로 정렬된 번호 목록
    vector<int> order(n);
    for (int i = 0; i < n; i++)
        order[i] = i;
    sort(order.begin(), order.end(), [&](int x, int y) {
        return tie(tasks[x].arrive, x) < tie(tasks[y].arrive, y);
    });

    // (우선순위, 도착시각, 번호) 가 가장 작은 것이 top 이 되도록 min-heap
    using Key = tuple<int, ll, int>;
    priority_queue<Key, vector<Key>, greater<Key>> ready;

    vector<ll> done(n);
    ll now = 0;
    int next = 0;      // order 에서 아직 도착 처리 안 된 첫 위치
    int last = -1;     // 직전에 실행한 태스크 (idle 은 갱신하지 않음)
    ll switches = 0;
    int finished = 0;

    while (finished < n) {
        while (next < n && tasks[order[next]].arrive <= now) {
            int id = order[next++];
            ready.push({tasks[id].prio, tasks[id].arrive, id});
        }
        if (ready.empty()) {
            now = tasks[order[next]].arrive; // idle: 다음 도착까지 점프
            continue;
        }

        int cur = get<2>(ready.top());
        if (last != -1 && last != cur)
            switches++;
        last = cur;

        // 현재 태스크가 끝나는 시각과 다음 도착 시각 중 빠른 쪽까지 실행
        ll run_until = now + tasks[cur].remain;
        if (next < n)
            run_until = min(run_until, tasks[order[next]].arrive);

        tasks[cur].remain -= run_until - now;
        now = run_until;
        if (tasks[cur].remain == 0) {
            ready.pop();
            done[cur] = now;
            finished++;
        }
        // 끝나지 않았으면 heap 에 그대로 두고, 새로 도착한 태스크와 다시 비교
    }

    ostringstream out;
    for (ll d : done)
        out << d << "\n";
    out << switches << "\n";
    return out.str();
}

static string run(const string &input)
{
    istringstream in(input);
    return solve(in);
}

int main()
{
    // 문제 예시
    assert(run("3\n0 5 4\n1 1 2\n2 3 1\n") == "7\n3\n4\n3\n");

    // 단일 태스크, 늦게 도착
    assert(run("1\n10 0 5\n") == "15\n0\n");

    // idle 구간 후 같은 태스크가 아니라 다른 태스크 → switch 1
    assert(run("2\n0 1 2\n5 1 3\n") == "2\n8\n1\n");

    // 같은 우선순위는 선점하지 않음 (도착 빠른 쪽 유지)
    assert(run("2\n0 2 3\n1 2 1\n") == "3\n4\n1\n");

    // 같은 우선순위·같은 도착 → 번호 작은 쪽 먼저
    assert(run("2\n0 1 1\n0 1 1\n") == "1\n2\n1\n");

    // 낮은 우선순위가 먼저 도착해도 높은 우선순위가 오면 선점, 이후 복귀
    assert(run("3\n0 9 10\n2 1 1\n4 1 1\n") == "12\n3\n5\n4\n");

    // 큰 시각: int 범위 초과 여부
    assert(run("2\n1000000000 0 10000\n1000000000 1 10000\n") ==
           "1000010000\n1000020000\n1\n");

    cout << "06_task_scheduler: OK\n";
    return 0;
}
