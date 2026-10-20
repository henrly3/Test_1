/*
 * 배열 기반 우선순위 큐 (최대 힙)
 *
 * - 배열 인덱스 0을 루트로 사용
 * - 부모: (i - 1) / 2, 왼쪽 자식: 2i + 1, 오른쪽 자식: 2i + 2
 * - 삽입/삭제: O(log n), 최댓값 조회: O(1)
 */
#include <stdio.h>
#include <stdbool.h>

#define MAX_SIZE 100

typedef struct {
    int priority;
    char data;
} Element;

typedef struct {
    Element heap[MAX_SIZE];
    int size;
} PriorityQueue;

void pq_init(PriorityQueue *pq) {
    pq->size = 0;
}

bool pq_is_empty(const PriorityQueue *pq) {
    return pq->size == 0;
}

bool pq_is_full(const PriorityQueue *pq) {
    return pq->size == MAX_SIZE;
}

static void swap(Element *a, Element *b) {
    Element tmp = *a;
    *a = *b;
    *b = tmp;
}

/* 새 원소를 맨 끝에 넣고 부모보다 크면 위로 올린다 */
bool pq_push(PriorityQueue *pq, int priority, char data) {
    if (pq_is_full(pq)) {
        return false;
    }

    int i = pq->size++;
    pq->heap[i].priority = priority;
    pq->heap[i].data = data;

    while (i > 0) {
        int parent = (i - 1) / 2;
        if (pq->heap[parent].priority >= pq->heap[i].priority) {
            break;
        }
        swap(&pq->heap[parent], &pq->heap[i]);
        i = parent;
    }
    return true;
}

/* 루트(최댓값)를 꺼내고, 마지막 원소를 루트로 옮겨 아래로 내린다 */
bool pq_pop(PriorityQueue *pq, Element *out) {
    if (pq_is_empty(pq)) {
        return false;
    }

    *out = pq->heap[0];
    pq->heap[0] = pq->heap[--pq->size];

    int i = 0;
    while (true) {
        int left = 2 * i + 1;
        int right = 2 * i + 2;
        int largest = i;

        if (left < pq->size && pq->heap[left].priority > pq->heap[largest].priority) {
            largest = left;
        }
        if (right < pq->size && pq->heap[right].priority > pq->heap[largest].priority) {
            largest = right;
        }
        if (largest == i) {
            break;
        }
        swap(&pq->heap[i], &pq->heap[largest]);
        i = largest;
    }
    return true;
}

bool pq_peek(const PriorityQueue *pq, Element *out) {
    if (pq_is_empty(pq)) {
        return false;
    }
    *out = pq->heap[0];
    return true;
}

int main(void) {
    PriorityQueue pq;
    Element e;

    pq_init(&pq);

    pq_push(&pq, 3, 'C');
    pq_push(&pq, 10, 'A');
    pq_push(&pq, 1, 'E');
    pq_push(&pq, 7, 'B');
    pq_push(&pq, 2, 'D');

    if (pq_peek(&pq, &e)) {
        printf("peek: %c (priority %d)\n", e.data, e.priority);
    }

    printf("pop 순서:\n");
    while (pq_pop(&pq, &e)) {
        printf("  %c (priority %d)\n", e.data, e.priority);
    }

    return 0;
}
