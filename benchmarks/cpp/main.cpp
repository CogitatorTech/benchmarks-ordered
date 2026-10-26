#include "common.h"
#include <map>
#include <set>
#include <absl/container/btree_map.h>
#include <absl/container/btree_set.h>

template<class Collection, bool IsSet>
static void measure(const Dataset &data, bool emit) {
    Collection collection;
    uint64_t times[5], start = now_ns();
    for (size_t i = 0; i < data.n; ++i) {
        int64_t key = data.insert[i];
        if constexpr (IsSet) collection.insert(key);
        else collection.insert_or_assign(key, key + 1);
    }
    times[0] = now_ns() - start;
    CHECK(collection.size() == data.n);
    size_t index = 0;
    for (const auto &entry : collection) {
        if constexpr (IsSet) CHECK(entry == (int64_t)(index * 2));
        else CHECK(entry.first == (int64_t)(index * 2) && entry.second == entry.first + 1);
        ++index;
    }
    CHECK(index == data.n);
    if (data.n) {
        if constexpr (IsSet) collection.insert(0);
        else {
            collection.insert_or_assign(0, -1);
            CHECK(collection.find(0)->second == -1);
            collection.insert_or_assign(0, 1);
        }
        CHECK(collection.size() == data.n);
    }
    CHECK(collection.erase(-1) == 0);
    auto reset = [&]() {
        collection = Collection{};
        for (size_t i = 0; i < data.n; ++i) {
            auto key = data.insert[i];
            if constexpr (IsSet) collection.insert(key);
            else collection.insert_or_assign(key, key + 1);
        }
        CHECK(collection.size() == data.n);
        size_t index = 0;
        for (const auto &entry : collection) {
            if constexpr (IsSet) CHECK(entry == (int64_t)(index * 2));
            else CHECK(entry.first == (int64_t)(index * 2) && entry.second == entry.first + 1);
            ++index;
        }
        CHECK(index == data.n);
    };
    const uint64_t expected = data.n * (IsSet ? data.n - (data.n != 0) : data.n);
    uint64_t sum = 0;
    reset();
    start = now_ns();
    for (size_t i = 0; i < data.n; ++i) {
        auto it = collection.find(data.lookup[i]);
        if (it != collection.end()) {
            if constexpr (IsSet) sum += *it + 1;
            else sum += it->second;
        }
    }
    times[1] = now_ns() - start;
    CHECK(sum == data.n * data.n);
    sum = 0;
    reset();
    start = now_ns();
    for (size_t i = 0; i < data.n; ++i) sum += collection.find(data.lookup[i] + 1) != collection.end();
    times[2] = now_ns() - start;
    CHECK(sum == 0);
    sum = 0;
    reset();
    start = now_ns();
    for (const auto &entry : collection) {
        if constexpr (IsSet) sum += entry;
        else sum += entry.second;
    }
    times[3] = now_ns() - start;
    CHECK(sum == expected);
    sum = 0;
    reset();
    start = now_ns();
    for (size_t i = 0; i < data.n; ++i) sum += collection.erase(data.remove[i]);
    times[4] = now_ns() - start;
    CHECK(sum == data.n && collection.empty());
    if (emit) report(times);
}

int main(int argc, char **argv) {
    CHECK(argc == 5);
    Dataset data = load(argv[2]);
    unsigned warmups = parse_repeats(argv[3], 0), samples = parse_repeats(argv[4], 1);
    for (unsigned i = 0; i < warmups + samples; ++i) {
        bool emit = i >= warmups;
        if (!strcmp(argv[1], "std_map")) measure<std::map<int64_t, int64_t>, false>(data, emit);
        else if (!strcmp(argv[1], "std_set")) measure<std::set<int64_t>, true>(data, emit);
        else if (!strcmp(argv[1], "absl_map")) measure<absl::btree_map<int64_t, int64_t>, false>(data, emit);
        else if (!strcmp(argv[1], "absl_set")) measure<absl::btree_set<int64_t>, true>(data, emit);
        else CHECK(0);
    }
    free(data.insert);
}
