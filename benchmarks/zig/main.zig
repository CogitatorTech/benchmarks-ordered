const std = @import("std");
const ordered = @import("ordered");
extern "c" fn printf([*:0]const u8, ...) c_int;
const allocator = std.heap.c_allocator;

fn compare(a: i64, b: i64) std.math.Order {
    return std.math.order(a, b);
}
const BTree = ordered.BTreeMap(i64, i64, compare, 16);
const Cartesian = ordered.CartesianTreeMap(i64, i64, compare);
const SkipList = ordered.SkipListMap(i64, i64, compare, 16);
const Sorted = ordered.SortedSet(i64, compare);
const RedBlack = ordered.RedBlackTreeSet(i64, compare);

fn Treap(comptime is_set: bool) type {
    return struct {
        const Self = @This();
        const Tree = std.Treap(i64, compare);
        const Node = struct { node: Tree.Node, value: if (is_set) void else i64 };
        tree: Tree = .{},
        len: usize = 0,
        fn init(_: std.mem.Allocator) Self {
            return .{};
        }
        fn deinit(self: *Self) void {
            while (self.tree.getMin()) |node| _ = self.remove(node.key);
        }
        fn count(self: *Self) usize {
            return self.len;
        }
        fn put(self: *Self, key: i64, value: i64) !void {
            var entry = self.tree.getEntryFor(key);
            if (entry.node) |node| {
                if (!is_set) {
                    const parent: *Node = @fieldParentPtr("node", node);
                    parent.value = value;
                }
            } else {
                const node = try allocator.create(Node);
                if (!is_set) node.value = value;
                entry.set(&node.node);
                self.len += 1;
            }
        }
        fn get(self: *Self, key: i64) ?i64 {
            const node = self.tree.getEntryFor(key).node orelse return null;
            if (is_set) return node.key;
            const parent: *Node = @fieldParentPtr("node", node);
            return parent.value;
        }
        fn remove(self: *Self, key: i64) ?i64 {
            var entry = self.tree.getEntryFor(key);
            const node = entry.node orelse return null;
            const parent: *Node = @fieldParentPtr("node", node);
            const value = if (is_set) node.key else parent.value;
            entry.set(null);
            allocator.destroy(parent);
            self.len -= 1;
            return value;
        }
    };
}

fn check(ok: bool) !void {
    if (!ok) return error.BenchmarkMismatch;
}
fn now() i96 {
    return std.Io.Timestamp.now(std.Options.debug_io, .real).nanoseconds;
}
fn isSet(comptime T: type) bool {
    return T == Sorted or T == RedBlack or T == Treap(true);
}
fn put(comptime T: type, collection: *T, key: i64, value: i64) !void {
    if (T == Sorted or T == RedBlack) {
        _ = try collection.put(key);
    } else try collection.put(key, value);
}
fn get(comptime T: type, collection: *T, key: i64) ?i64 {
    if (T == Treap(true) or T == Treap(false)) return collection.get(key);
    if (comptime isSet(T)) return if (collection.contains(key)) key else null;
    const value = collection.getPtr(key) orelse return null;
    return value.*;
}
fn remove(comptime T: type, collection: *T, key: i64) ?i64 {
    if (T == Sorted) return collection.removeValue(key);
    return collection.remove(key);
}

fn visit(comptime is_set: bool, key: i64, value: i64, index: *usize, sum: *i64, comptime validate: bool) !void {
    if (validate) {
        try check(key == @as(i64, @intCast(index.* * 2)));
        if (!is_set) try check(value == key + 1);
        index.* += 1;
    }
    sum.* += if (is_set) key else value;
}

fn iterate(comptime T: type, collection: *T, comptime validate: bool) !i64 {
    var sum: i64 = 0;
    var index: usize = 0;
    if (T == Treap(true) or T == Treap(false)) {
        var it = collection.tree.inorderIterator();
        while (it.next()) |node| {
            const parent: *T.Node = @fieldParentPtr("node", node);
            try visit(isSet(T), node.key, if (comptime isSet(T)) 0 else parent.value, &index, &sum, validate);
        }
    } else if (T == Sorted) {
        var it = collection.iterator();
        while (it.next()) |key| try visit(true, key, 0, &index, &sum, validate);
    } else if (T == SkipList) {
        var it = collection.iterator();
        while (it.next()) |entry| try visit(false, entry.key, entry.value, &index, &sum, validate);
    } else {
        var it = if (T == Cartesian) try collection.iterator(allocator) else try collection.iterator();
        defer it.deinit();
        while (try it.next()) |entry| {
            if (T == RedBlack) {
                try visit(true, entry, 0, &index, &sum, validate);
            } else try visit(false, entry.key, entry.value, &index, &sum, validate);
        }
    }
    if (validate) try check(index == collection.count());
    return sum;
}

fn reset(comptime T: type, collection: *T, keys: []const i64, n: usize) !void {
    collection.deinit();
    collection.* = if (T == SkipList) try T.init(allocator) else T.init(allocator);
    for (keys[0..n]) |key| try put(T, collection, key, key + 1);
    try check(collection.count() == n);
    _ = try iterate(T, collection, true);
}

fn measure(comptime T: type, keys: []const i64, n: usize, emit: bool) !void {
    var collection = if (T == SkipList) try T.init(allocator) else T.init(allocator);
    defer collection.deinit();
    var times: [5]u64 = undefined;
    var start = now();
    for (keys[0..n]) |key| try put(T, &collection, key, key + 1);
    times[0] = @intCast(now() - start);
    try check(collection.count() == n);
    _ = try iterate(T, &collection, true);
    if (n > 0) {
        try put(T, &collection, 0, -1);
        try check(get(T, &collection, 0) == (if (comptime isSet(T)) @as(i64, 0) else -1));
        try put(T, &collection, 0, 1);
        try check(collection.count() == n);
    }
    try check(remove(T, &collection, -1) == null);
    const size: i64 = @intCast(n);
    const expected = if (comptime isSet(T)) size * (size - 1) else size * size;
    var sum: i64 = 0;
    try reset(T, &collection, keys, n);
    start = now();
    for (keys[n .. n * 2]) |key| {
        if (get(T, &collection, key)) |value| sum += value + @as(i64, @intFromBool(isSet(T)));
    }
    times[1] = @intCast(now() - start);
    try check(sum == size * size);
    sum = 0;
    try reset(T, &collection, keys, n);
    start = now();
    for (keys[n .. n * 2]) |key| sum += @intFromBool(get(T, &collection, key + 1) != null);
    times[2] = @intCast(now() - start);
    try check(sum == 0);
    try reset(T, &collection, keys, n);
    start = now();
    sum = try iterate(T, &collection, false);
    times[3] = @intCast(now() - start);
    try check(sum == expected);
    sum = 0;
    try reset(T, &collection, keys, n);
    start = now();
    for (keys[n * 2 ..]) |key| sum += @intFromBool(remove(T, &collection, key) != null);
    times[4] = @intCast(now() - start);
    try check(sum == size and collection.count() == 0);
    if (emit) {
        inline for (.{ "insert", "hit", "miss", "iterate", "remove" }, 0..) |phase, i| {
            _ = printf("%s,%llu\n", @as([*:0]const u8, phase), @as(c_ulonglong, times[i]));
        }
        _ = printf("\n");
    }
}

pub fn main(init: std.process.Init) !void {
    var args = std.process.Args.Iterator.init(init.minimal.args);
    defer args.deinit();
    _ = args.next();
    const name = args.next() orelse return error.MissingImplementation;
    const path = args.next() orelse return error.MissingFixture;
    const warmups = try std.fmt.parseInt(usize, args.next() orelse return error.MissingWarmups, 10);
    const samples = try std.fmt.parseInt(usize, args.next() orelse return error.MissingSamples, 10);
    try check(warmups <= 1000 and samples > 0 and samples <= 1000 and args.next() == null);
    const bytes = try std.Io.Dir.cwd().readFileAlloc(init.io, path, allocator, .limited(240_000_009));
    defer allocator.free(bytes);
    try check(bytes.len >= 8);
    const n: usize = @intCast(std.mem.readInt(u64, bytes[0..8], .little));
    try check(n <= 10_000_000 and bytes.len == 8 + n * 24);
    const keys = try allocator.alloc(i64, n * 3);
    defer allocator.free(keys);
    for (keys, 0..) |*key, i| {
        key.* = std.mem.readInt(i64, bytes[8 + i * 8 ..][0..8], .little);
        try check(key.* >= 0 and key.* < @as(i64, @intCast(n * 2)) and @mod(key.*, 2) == 0);
    }
    inline for (.{ BTree, Cartesian, SkipList, Sorted, RedBlack, Treap(false), Treap(true) }, .{ "btree_map", "cartesian_map", "skiplist_map", "sorted_set", "redblack_set", "treap_map", "treap_set" }) |T, label| {
        if (std.mem.eql(u8, name, label)) {
            for (0..warmups + samples) |i| try measure(T, keys, n, i >= warmups);
            return;
        }
    }
    return error.UnknownImplementation;
}
