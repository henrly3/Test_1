CC      = gcc
CXX     = g++
CFLAGS  = -std=c11 -Wall -Wextra -O2
CXXFLAGS = -std=c++17 -Wall -Wextra -O2

C_SRCS   = $(wildcard */solution.c) 07_c_quiz/check.c
CXX_SRCS = $(wildcard */solution.cpp)
BINS     = $(C_SRCS:.c=.out) $(CXX_SRCS:.cpp=.out)

.PHONY: all test clean

all: $(BINS)

%.out: %.c
	$(CC) $(CFLAGS) $< -o $@

%.out: %.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

test: all
	@for b in $(BINS); do echo "== $$b"; ./$$b || exit 1; done
	@echo "ALL TESTS PASSED"

clean:
	rm -f $(BINS)
