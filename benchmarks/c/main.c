#include "common.h"
#include "kbtree.h"

#ifdef BENCH_SET
typedef int64_t Item;
static Item item(int64_t key, int64_t value) { (void)value; return key; }
static int64_t key_of(Item entry) { return entry; }
static int64_t value_of(Item entry) { return entry; }
#else
typedef struct { int64_t key, value; } Item;
static Item item(int64_t key, int64_t value) { Item entry = {key, value}; return entry; }
static int64_t key_of(Item entry) { return entry.key; }
static int64_t value_of(Item entry) { return entry.value; }
#endif

#define compare(a, b) ((key_of(a) > key_of(b)) - (key_of(a) < key_of(b)))
KBTREE_INIT(items, Item, compare)

static void put(kbtree_t(items) *tree, int64_t key, int64_t value) {
    Item entry = item(key, value);
    Item *existing = kb_get(items, tree, entry);
    if (existing) *existing = entry;
    else kb_put(items, tree, entry);
}

static int remove_key(kbtree_t(items) *tree, int64_t key) {
    Item entry = item(key, 0);
    if (!kb_get(items, tree, entry)) return 0;
    (void)kb_del(items, tree, entry);
    return 1;
}

static void validate(kbtree_t(items) *tree, const Dataset *data) {
    CHECK((size_t)kb_size(tree) == data->n);
    kbitr_t it;
    size_t index = 0;
    if (data->n) {
        kb_itr_first(items, tree, &it);
        while (kb_itr_valid(&it)) {
            Item entry = kb_itr_key(Item, &it);
            CHECK(key_of(entry) == (int64_t)(index * 2));
            CHECK(value_of(entry) == value_of(item((int64_t)(index * 2), (int64_t)(index * 2 + 1))));
            ++index;
            kb_itr_next(items, tree, &it);
        }
    }
    CHECK(index == data->n);
}

static void reset(kbtree_t(items) **tree, const Dataset *data) {
    kb_destroy(items, (*tree));
    *tree = kb_init(items, 512);
    CHECK(*tree != NULL);
    for (size_t i = 0; i < data->n; ++i) put(*tree, data->insert[i], data->insert[i] + 1);
    validate(*tree, data);
}

static void measure(const Dataset *data, int emit) {
    kbtree_t(items) *tree = kb_init(items, 512);
    CHECK(tree != NULL);
    uint64_t times[5], start = now_ns();
    for (size_t i = 0; i < data->n; ++i) put(tree, data->insert[i], data->insert[i] + 1);
    times[0] = now_ns() - start;
    validate(tree, data);
    kbitr_t it;
    if (data->n) {
        put(tree, 0, -1);
        CHECK(value_of(*kb_get(items, tree, item(0, 0))) == value_of(item(0, -1)));
        put(tree, 0, 1);
        CHECK((size_t)kb_size(tree) == data->n);
    }
    CHECK(!remove_key(tree, -1));
    uint64_t expected = 0;
    for (size_t i = 0; i < data->n; ++i) expected += value_of(item(i * 2, i * 2 + 1));
    uint64_t sum = 0;
    reset(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) {
        Item *entry = kb_get(items, tree, item(data->lookup[i], 0));
        if (entry) {
            sum += value_of(*entry);
#ifdef BENCH_SET
            sum++;
#endif
        }
    }
    times[1] = now_ns() - start;
    CHECK(sum == data->n * data->n);
    sum = 0;
    reset(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += kb_get(items, tree, item(data->lookup[i] + 1, 0)) != NULL;
    times[2] = now_ns() - start;
    CHECK(sum == 0);
    sum = 0;
    reset(&tree, data);
    start = now_ns();
    if (data->n) {
        kb_itr_first(items, tree, &it);
        while (kb_itr_valid(&it)) {
            sum += value_of(kb_itr_key(Item, &it));
            kb_itr_next(items, tree, &it);
        }
    }
    times[3] = now_ns() - start;
    CHECK(sum == expected);
    sum = 0;
    reset(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += remove_key(tree, data->remove[i]);
    times[4] = now_ns() - start;
    CHECK(sum == data->n && kb_size(tree) == 0);
    kb_destroy(items, tree);
    if (emit) report(times);
}

int main(int argc, char **argv) {
    CHECK(argc == 5);
#ifdef BENCH_SET
    CHECK(!strcmp(argv[1], "kbtree_set"));
#else
    CHECK(!strcmp(argv[1], "kbtree_map"));
#endif
    Dataset data = load(argv[2]);
    unsigned warmups = parse_repeats(argv[3], 0), samples = parse_repeats(argv[4], 1);
    for (unsigned i = 0; i < warmups + samples; ++i) measure(&data, i >= warmups);
    free(data.insert);
    return 0;
}
