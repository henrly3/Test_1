#include <algorithm>
#include <cassert>
#include <functional>
#include <iostream>
#include <queue>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

// 입력 스트림을 받아 결과 문자열을 돌려준다 (실제 시험에서는 cin/cout 직접 사용)
string solve(istream &in)
{
    int n, m, t, k;
    in >> n >> m >> t >> k;
    vector<vector<int>> g(n, vector<int>(m));
    for (auto &row : g)
        for (int &v : row)
            in >> v;

    const int dr[] = {-1, 1, 0, 0};
    const int dc[] = {0, 0, -1, 1};
    vector<int> sizes;

    for (int r = 0; r < n; r++) {
        for (int c = 0; c < m; c++) {
            if (g[r][c] < t)
                continue;
            // BFS: 방문한 칸은 -1 로 덮어 visited 배열을 대신한다
            queue<pair<int, int>> q;
            q.push({r, c});
            g[r][c] = -1;
            int cnt = 0;
            while (!q.empty()) {
                auto [cr, cc] = q.front();
                q.pop();
                cnt++;
                for (int d = 0; d < 4; d++) {
                    int nr = cr + dr[d], nc = cc + dc[d];
                    if (nr < 0 || nr >= n || nc < 0 || nc >= m || g[nr][nc] < t)
                        continue;
                    g[nr][nc] = -1;
                    q.push({nr, nc});
                }
            }
            if (cnt >= k)
                sizes.push_back(cnt);
        }
    }

    sort(sizes.begin(), sizes.end(), greater<int>());
    ostringstream out;
    out << sizes.size() << "\n";
    for (size_t i = 0; i < sizes.size(); i++)
        out << sizes[i] << (i + 1 < sizes.size() ? " " : "\n");
    return out.str();
}

static string run(const string &input)
{
    istringstream in(input);
    return solve(in);
}

int main()
{
    assert(run("5 6 100 2\n"
               "120 130   0   0   0 200\n"
               "  0 110   0  90   0 210\n"
               "  0   0   0 150   0   0\n"
               " 99   0 101 160 170   0\n"
               "  0   0   0   0   0 255\n") == "3\n4 3 2\n");

    // 표적 없음
    assert(run("2 2 10 1\n0 0\n0 0\n") == "0\n");
    // 전부 잡음
    assert(run("3 3 1 2\n1 0 1\n0 1 0\n1 0 1\n") == "0\n");
    // 대각선은 연결이 아님, K=1
    assert(run("2 2 1 1\n1 0\n0 1\n") == "2\n1 1\n");
    // T=0 이면 모든 칸이 탐지 칸
    assert(run("2 3 0 1\n0 0 0\n0 0 0\n") == "1\n6\n");

    // 큰 입력: 1000x1000 전부 탐지 → 재귀 DFS 였다면 스택 오버플로 위험
    {
        string big = "1000 1000 1 1\n";
        big.reserve(2100000);
        for (int i = 0; i < 1000; i++) {
            for (int j = 0; j < 1000; j++)
                big += "1 ";
            big += "\n";
        }
        assert(run(big) == "1\n1000000\n");
    }

    cout << "05_radar_grid: OK\n";
    return 0;
}
