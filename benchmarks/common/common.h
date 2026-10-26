#ifndef ORDERED_BENCH_COMMON_H
#define ORDERED_BENCH_COMMON_H
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <inttypes.h>

#define CHECK(ok) do { if (!(ok)) { fprintf(stderr, "Check failed at %s:%d: %s\n", __FILE__, __LINE__, #ok); exit(1); } } while (0)

typedef struct { size_t n; int64_t *insert, *lookup, *remove; } Dataset;

static uint64_t read_u64(FILE *file) {
    unsigned char bytes[8];
    CHECK(fread(bytes, 1, 8, file) == 8);
    uint64_t value = 0;
    for (int i = 0; i < 8; ++i) value |= (uint64_t)bytes[i] << (8 * i);
    return value;
}

static Dataset load(const char *path) {
    FILE *file = fopen(path, "rb");
    CHECK(file != NULL);
    uint64_t n = read_u64(file);
    CHECK(n <= 10000000);
    Dataset data;
    data.n = (size_t)n;
    data.insert = (int64_t *)malloc((n * 3 + 1) * sizeof(int64_t));
    CHECK(data.insert != NULL);
    data.lookup = data.insert + n;
    data.remove = data.lookup + n;
    for (size_t i = 0; i < n * 3; ++i) {
        uint64_t key = read_u64(file);
        CHECK(key < n * 2 && key % 2 == 0);
        data.insert[i] = (int64_t)key;
    }
    CHECK(fgetc(file) == EOF && !ferror(file));
    CHECK(fclose(file) == 0);
    return data;
}

static uint64_t now_ns(void) {
    struct timespec t;
    CHECK(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}

static void report(const uint64_t times[5]) {
    const char *phases[] = {"insert", "hit", "miss", "iterate", "remove"};
    for (int i = 0; i < 5; ++i) printf("%s,%" PRIu64 "\n", phases[i], times[i]);
    putchar('\n');
}

static unsigned parse_repeats(const char *arg, unsigned minimum) {
    char *end;
    unsigned long n = strtoul(arg, &end, 10);
    CHECK(*arg && !*end && n >= minimum && n <= 1000);
    return (unsigned)n;
}
#endif
