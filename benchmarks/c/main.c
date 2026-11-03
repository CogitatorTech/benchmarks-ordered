#include "common.h"
#include "kbtree.h"
#include "kavl.h"
#include "btree.h"

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

static void kb_put_entry(kbtree_t(items) *tree, int64_t key, int64_t value) {
    Item entry = item(key, value);
    Item *existing = kb_get(items, tree, entry);
    if (existing) *existing = entry;
    else kb_put(items, tree, entry);
}

static int kb_remove_entry(kbtree_t(items) *tree, int64_t key) {
    Item entry = item(key, 0);
    if (!kb_get(items, tree, entry)) return 0;
    (void)kb_del(items, tree, entry);
    return 1;
}

static void kb_validate_tree(kbtree_t(items) *tree, const Dataset *data) {
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

static void kb_reset_tree(kbtree_t(items) **tree, const Dataset *data) {
    kb_destroy(items, (*tree));
    *tree = kb_init(items, 512);
    CHECK(*tree != NULL);
    for (size_t i = 0; i < data->n; ++i) kb_put_entry(*tree, data->insert[i], data->insert[i] + 1);
    kb_validate_tree(*tree, data);
}

static void measure_kbtree(const Dataset *data, int emit) {
    kbtree_t(items) *tree = kb_init(items, 512);
    CHECK(tree != NULL);
    uint64_t times[5], start = now_ns();
    for (size_t i = 0; i < data->n; ++i) kb_put_entry(tree, data->insert[i], data->insert[i] + 1);
    times[0] = now_ns() - start;
    kb_validate_tree(tree, data);
    kbitr_t it;
    if (data->n) {
        kb_put_entry(tree, 0, -1);
        CHECK(value_of(*kb_get(items, tree, item(0, 0))) == value_of(item(0, -1)));
        kb_put_entry(tree, 0, 1);
        CHECK((size_t)kb_size(tree) == data->n);
    }
    CHECK(!kb_remove_entry(tree, -1));
    uint64_t expected = 0;
    for (size_t i = 0; i < data->n; ++i) expected += value_of(item(i * 2, i * 2 + 1));
    uint64_t sum = 0;
    kb_reset_tree(&tree, data);
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
    kb_reset_tree(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += kb_get(items, tree, item(data->lookup[i] + 1, 0)) != NULL;
    times[2] = now_ns() - start;
    CHECK(sum == 0);
    sum = 0;
    kb_reset_tree(&tree, data);
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
    kb_reset_tree(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += kb_remove_entry(tree, data->remove[i]);
    times[4] = now_ns() - start;
    CHECK(sum == data->n && kb_size(tree) == 0);
    kb_destroy(items, tree);
    if (emit) report(times);
}

struct KavlNode {
    int64_t key;
#ifndef BENCH_SET
    int64_t value;
#endif
    KAVL_HEAD(struct KavlNode) head;
};

#define kavl_node_cmp(p, q) (((q)->key < (p)->key) - ((p)->key < (q)->key))
KAVL_INIT(avl, struct KavlNode, head, kavl_node_cmp)

static void kavl_put_entry(struct KavlNode **root, int64_t key, int64_t value) {
#ifdef BENCH_SET
    (void)value;
#endif
    struct KavlNode *p = (struct KavlNode *)malloc(sizeof(*p));
    CHECK(p != NULL);
    p->key = key;
#ifndef BENCH_SET
    p->value = value;
#endif
    struct KavlNode *q = kavl_insert(avl, root, p, 0);
    if (q != p) {
#ifndef BENCH_SET
        q->value = value;
#endif
        free(p);
    }
}

static const struct KavlNode *kavl_get_entry(struct KavlNode *root, int64_t key) {
    struct KavlNode target;
    target.key = key;
    return kavl_find(avl, root, &target, 0);
}

static int kavl_remove_entry(struct KavlNode **root, int64_t key) {
    struct KavlNode target;
    target.key = key;
    struct KavlNode *erased = kavl_erase(avl, root, &target, 0);
    if (erased) {
        free(erased);
        return 1;
    }
    return 0;
}

static void kavl_validate_tree(struct KavlNode *root, const Dataset *data) {
    CHECK((size_t)kavl_size(head, root) == data->n);
    size_t index = 0;
    if (data->n) {
        kavl_itr_t(avl) it;
        kavl_itr_first(avl, root, &it);
        const struct KavlNode *p;
        while ((p = kavl_at(&it)) != NULL) {
            CHECK(p->key == (int64_t)(index * 2));
#ifndef BENCH_SET
            CHECK(p->value == (int64_t)(index * 2 + 1));
#endif
            ++index;
            if (!kavl_itr_next(avl, &it)) break;
        }
    }
    CHECK(index == data->n);
}

static void kavl_reset_tree(struct KavlNode **root, const Dataset *data) {
    kavl_free(struct KavlNode, head, *root, free);
    *root = NULL;
    for (size_t i = 0; i < data->n; ++i) kavl_put_entry(root, data->insert[i], data->insert[i] + 1);
    kavl_validate_tree(*root, data);
}

static void measure_kavl(const Dataset *data, int emit) {
    struct KavlNode *root = NULL;
    uint64_t times[5], start = now_ns();
    for (size_t i = 0; i < data->n; ++i) kavl_put_entry(&root, data->insert[i], data->insert[i] + 1);
    times[0] = now_ns() - start;
    kavl_validate_tree(root, data);
    if (data->n) {
        kavl_put_entry(&root, 0, -1);
        const struct KavlNode *check_node = kavl_get_entry(root, 0);
        CHECK(check_node != NULL);
#ifndef BENCH_SET
        CHECK(check_node->value == -1);
#endif
        kavl_put_entry(&root, 0, 1);
        CHECK((size_t)kavl_size(head, root) == data->n);
    }
    CHECK(!kavl_remove_entry(&root, -1));
    uint64_t expected = 0;
    for (size_t i = 0; i < data->n; ++i) expected += value_of(item(i * 2, i * 2 + 1));
    uint64_t sum = 0;
    kavl_reset_tree(&root, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) {
        const struct KavlNode *entry = kavl_get_entry(root, data->lookup[i]);
        if (entry) {
#ifdef BENCH_SET
            sum += entry->key + 1;
#else
            sum += entry->value;
#endif
        }
    }
    times[1] = now_ns() - start;
    CHECK(sum == data->n * data->n);
    sum = 0;
    kavl_reset_tree(&root, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += kavl_get_entry(root, data->lookup[i] + 1) != NULL;
    times[2] = now_ns() - start;
    CHECK(sum == 0);
    sum = 0;
    kavl_reset_tree(&root, data);
    start = now_ns();
    if (data->n) {
        kavl_itr_t(avl) it;
        kavl_itr_first(avl, root, &it);
        const struct KavlNode *p;
        while ((p = kavl_at(&it)) != NULL) {
#ifdef BENCH_SET
            sum += p->key;
#else
            sum += p->value;
#endif
            if (!kavl_itr_next(avl, &it)) break;
        }
    }
    times[3] = now_ns() - start;
    CHECK(sum == expected);
    sum = 0;
    kavl_reset_tree(&root, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += kavl_remove_entry(&root, data->remove[i]);
    times[4] = now_ns() - start;
    CHECK(sum == data->n && kavl_size(head, root) == 0);
    kavl_free(struct KavlNode, head, root, free);
    if (emit) report(times);
}

static int btree_compare_items(const void *a, const void *b, void *udata) {
    (void)udata;
    const Item *ia = (const Item *)a;
    const Item *ib = (const Item *)b;
    return (key_of(*ia) > key_of(*ib)) - (key_of(*ia) < key_of(*ib));
}

static void btree_put_entry(struct btree *tree, int64_t key, int64_t value) {
    Item entry = item(key, value);
    btree_set(tree, &entry);
}

static const Item *btree_get_entry(const struct btree *tree, int64_t key) {
    Item target = item(key, 0);
    return (const Item *)btree_get(tree, &target);
}

static int btree_remove_entry(struct btree *tree, int64_t key) {
    Item target = item(key, 0);
    return btree_delete(tree, &target) != NULL;
}

struct BtreeValidateCtx {
    size_t index;
};

static bool btree_validate_cb(const void *item_ptr, void *udata) {
    struct BtreeValidateCtx *ctx = (struct BtreeValidateCtx *)udata;
    const Item *entry = (const Item *)item_ptr;
    CHECK(key_of(*entry) == (int64_t)(ctx->index * 2));
    CHECK(value_of(*entry) == value_of(item((int64_t)(ctx->index * 2), (int64_t)(ctx->index * 2 + 1))));
    ctx->index++;
    return true;
}

static void btree_validate_tree(const struct btree *tree, const Dataset *data) {
    CHECK(btree_count(tree) == data->n);
    struct BtreeValidateCtx ctx = { 0 };
    if (data->n) {
        btree_ascend(tree, NULL, btree_validate_cb, &ctx);
    }
    CHECK(ctx.index == data->n);
}

static void btree_reset_tree(struct btree **tree, const Dataset *data) {
    btree_free(*tree);
    *tree = btree_new(sizeof(Item), 0, btree_compare_items, NULL);
    CHECK(*tree != NULL);
    for (size_t i = 0; i < data->n; ++i) btree_put_entry(*tree, data->insert[i], data->insert[i] + 1);
    btree_validate_tree(*tree, data);
}

struct BtreeSumCtx {
    uint64_t sum;
};

static bool btree_sum_cb(const void *item_ptr, void *udata) {
    struct BtreeSumCtx *ctx = (struct BtreeSumCtx *)udata;
    const Item *entry = (const Item *)item_ptr;
#ifdef BENCH_SET
    ctx->sum += key_of(*entry);
#else
    ctx->sum += value_of(*entry);
#endif
    return true;
}

static void measure_btree(const Dataset *data, int emit) {
    struct btree *tree = btree_new(sizeof(Item), 0, btree_compare_items, NULL);
    CHECK(tree != NULL);
    uint64_t times[5], start = now_ns();
    for (size_t i = 0; i < data->n; ++i) btree_put_entry(tree, data->insert[i], data->insert[i] + 1);
    times[0] = now_ns() - start;
    btree_validate_tree(tree, data);
    if (data->n) {
        btree_put_entry(tree, 0, -1);
        const Item *check_entry = btree_get_entry(tree, 0);
        CHECK(check_entry != NULL);
        CHECK(value_of(*check_entry) == value_of(item(0, -1)));
        btree_put_entry(tree, 0, 1);
        CHECK(btree_count(tree) == data->n);
    }
    CHECK(!btree_remove_entry(tree, -1));
    uint64_t expected = 0;
    for (size_t i = 0; i < data->n; ++i) expected += value_of(item(i * 2, i * 2 + 1));
    uint64_t sum = 0;
    btree_reset_tree(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) {
        const Item *entry = btree_get_entry(tree, data->lookup[i]);
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
    btree_reset_tree(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += btree_get_entry(tree, data->lookup[i] + 1) != NULL;
    times[2] = now_ns() - start;
    CHECK(sum == 0);
    struct BtreeSumCtx ctx = { 0 };
    btree_reset_tree(&tree, data);
    start = now_ns();
    if (data->n) {
        btree_ascend(tree, NULL, btree_sum_cb, &ctx);
    }
    times[3] = now_ns() - start;
    CHECK(ctx.sum == expected);
    sum = 0;
    btree_reset_tree(&tree, data);
    start = now_ns();
    for (size_t i = 0; i < data->n; ++i) sum += btree_remove_entry(tree, data->remove[i]);
    times[4] = now_ns() - start;
    CHECK(sum == data->n && btree_count(tree) == 0);
    btree_free(tree);
    if (emit) report(times);
}

int main(int argc, char **argv) {
    CHECK(argc == 5);
    Dataset data = load(argv[2]);
    unsigned warmups = parse_repeats(argv[3], 0), samples = parse_repeats(argv[4], 1);
    for (unsigned i = 0; i < warmups + samples; ++i) {
        int emit = i >= warmups;
#ifdef BENCH_SET
        if (!strcmp(argv[1], "kbtree_set")) measure_kbtree(&data, emit);
        else if (!strcmp(argv[1], "kavl_set")) measure_kavl(&data, emit);
        else if (!strcmp(argv[1], "btree_set")) measure_btree(&data, emit);
        else CHECK(0);
#else
        if (!strcmp(argv[1], "kbtree_map")) measure_kbtree(&data, emit);
        else if (!strcmp(argv[1], "kavl_map")) measure_kavl(&data, emit);
        else if (!strcmp(argv[1], "btree_map")) measure_btree(&data, emit);
        else CHECK(0);
#endif
    }
    free(data.insert);
    return 0;
}
