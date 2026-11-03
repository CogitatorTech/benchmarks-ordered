package bench;

import it.unimi.dsi.fastutil.longs.Long2LongAVLTreeMap;
import it.unimi.dsi.fastutil.longs.Long2LongRBTreeMap;
import it.unimi.dsi.fastutil.longs.Long2LongSortedMap;
import it.unimi.dsi.fastutil.longs.LongAVLTreeSet;
import it.unimi.dsi.fastutil.longs.LongRBTreeSet;
import it.unimi.dsi.fastutil.longs.LongSortedSet;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.concurrent.TimeUnit;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.BenchmarkParams;

@State(Scope.Thread)
@BenchmarkMode(Mode.SingleShotTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 20, batchSize = 1)
@Measurement(iterations = 5, batchSize = 1)
@Fork(value = 2, jvmArgs = {"-Xms1g", "-Xmx1g"})
@Threads(1)
public class CollectionsBench {
    @Param({"tree_map", "tree_set", "fastutil_avl_map", "fastutil_avl_set", "fastutil_rb_map", "fastutil_rb_set"})
    public String implementation;
    @Param({"fixture.bin"})
    public String fixture;
    private boolean isSet;
    private boolean isFastutil;
    private int size;
    private Long[] insertion, values, lookup, absent, removal;
    private long[] rawInsertion, rawValues, rawLookup, rawAbsent, rawRemoval;
    private TreeMap<Long, Long> map;
    private TreeSet<Long> set;
    private Long2LongSortedMap fastMap;
    private LongSortedSet fastSet;
    private String phase;
    private long result;

    private static void check(boolean ok) {
        if (!ok) throw new IllegalStateException("Benchmark mismatch");
    }

    @Setup(Level.Trial)
    public void load() throws IOException {
        isSet = implementation.endsWith("set");
        isFastutil = implementation.startsWith("fastutil");
        byte[] bytes = Files.readAllBytes(Path.of(fixture));
        check(bytes.length >= 8);
        ByteBuffer data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        long count = data.getLong();
        check(count >= 0 && count <= 10_000_000 && bytes.length == 8 + count * 24);
        size = (int) count;
        insertion = new Long[size];
        values = new Long[size];
        lookup = new Long[size];
        absent = new Long[size];
        removal = new Long[size];
        rawInsertion = new long[size];
        rawValues = new long[size];
        rawLookup = new long[size];
        rawAbsent = new long[size];
        rawRemoval = new long[size];
        for (int i = 0; i < size; i++) {
            long k = readKey(data);
            rawInsertion[i] = k;
            rawValues[i] = k + 1;
            insertion[i] = k;
            values[i] = rawValues[i];
        }
        for (int i = 0; i < size; i++) {
            long k = readKey(data);
            rawLookup[i] = k;
            rawAbsent[i] = k + 1;
            lookup[i] = k;
            absent[i] = rawAbsent[i];
        }
        for (int i = 0; i < size; i++) {
            long k = readKey(data);
            rawRemoval[i] = k;
            removal[i] = k;
        }
        fresh();
        populate();
        validate();
        if (size > 0) {
            if (isFastutil) {
                if (isSet) {
                    fastSet.add(0L);
                    check(fastSet.size() == size);
                } else {
                    fastMap.put(0L, -1L);
                    check(fastMap.size() == size && fastMap.get(0L) == -1L);
                    fastMap.put(0L, 1L);
                }
            } else {
                if (isSet) {
                    set.add(0L);
                    check(set.size() == size);
                } else {
                    map.put(0L, -1L);
                    check(map.size() == size && map.get(0L) == -1L);
                    map.put(0L, 1L);
                }
            }
        }
        if (isFastutil) {
            check(isSet ? !fastSet.remove(-1L) : fastMap.remove(-1L) == fastMap.defaultReturnValue());
        } else {
            check(isSet ? !set.remove(-1L) : map.remove(-1L) == null);
        }
    }

    private long readKey(ByteBuffer data) {
        long key = data.getLong();
        check(key >= 0 && key < size * 2L && key % 2 == 0);
        return key;
    }

    private void fresh() {
        switch (implementation) {
            case "tree_set" -> set = new TreeSet<>();
            case "tree_map" -> map = new TreeMap<>();
            case "fastutil_avl_set" -> fastSet = new LongAVLTreeSet();
            case "fastutil_avl_map" -> {
                fastMap = new Long2LongAVLTreeMap();
                fastMap.defaultReturnValue(Long.MIN_VALUE);
            }
            case "fastutil_rb_set" -> fastSet = new LongRBTreeSet();
            case "fastutil_rb_map" -> {
                fastMap = new Long2LongRBTreeMap();
                fastMap.defaultReturnValue(Long.MIN_VALUE);
            }
            default -> throw new IllegalArgumentException("Unknown implementation: " + implementation);
        }
    }

    private void populate() {
        if (isFastutil) {
            if (isSet) {
                for (long key : rawInsertion) fastSet.add(key);
            } else {
                for (int i = 0; i < size; i++) fastMap.put(rawInsertion[i], rawValues[i]);
            }
        } else {
            if (isSet) {
                for (Long key : insertion) set.add(key);
            } else {
                for (int i = 0; i < size; i++) map.put(insertion[i], values[i]);
            }
        }
    }

    private void validate() {
        int currentSize = isFastutil ? (isSet ? fastSet.size() : fastMap.size()) : (isSet ? set.size() : map.size());
        check(currentSize == size);
        long index = 0;
        if (isFastutil) {
            if (isSet) {
                for (var it = fastSet.iterator(); it.hasNext(); ) {
                    check(it.nextLong() == index++ * 2);
                }
            } else {
                for (var it = fastMap.long2LongEntrySet().iterator(); it.hasNext(); ) {
                    var entry = it.next();
                    check(entry.getLongKey() == index++ * 2);
                    check(entry.getLongValue() == entry.getLongKey() + 1);
                }
            }
        } else {
            if (isSet) {
                for (Long key : set) check(key == index++ * 2);
            } else {
                for (var entry : map.entrySet()) {
                    check(entry.getKey() == index++ * 2);
                    check(entry.getValue() == entry.getKey() + 1);
                }
            }
        }
        check(index == size);
    }

    @Setup(Level.Iteration)
    public void prepare(BenchmarkParams params) {
        phase = params.getBenchmark().substring(params.getBenchmark().lastIndexOf('.') + 1);
        preparePhase(phase);
    }

    private void preparePhase(String name) {
        phase = name;
        result = Long.MIN_VALUE;
        fresh();
        if (!phase.equals("insert")) {
            populate();
            validate();
        }
    }

    @Benchmark
    public long insert() {
        populate();
        return result = isFastutil ? (isSet ? fastSet.size() : fastMap.size()) : (isSet ? set.size() : map.size());
    }

    @Benchmark
    public long hit() {
        long sum = 0;
        if (isFastutil) {
            if (isSet) {
                for (long key : rawLookup) if (fastSet.contains(key)) sum += key + 1;
            } else {
                for (long key : rawLookup) {
                    long value = fastMap.get(key);
                    if (value != fastMap.defaultReturnValue()) sum += value;
                }
            }
        } else {
            if (isSet) {
                for (Long key : lookup) if (set.contains(key)) sum += key + 1;
            } else {
                for (Long key : lookup) {
                    Long value = map.get(key);
                    if (value != null) sum += value;
                }
            }
        }
        return result = sum;
    }

    @Benchmark
    public long miss() {
        long hits = 0;
        if (isFastutil) {
            if (isSet) {
                for (long key : rawAbsent) if (fastSet.contains(key)) hits++;
            } else {
                for (long key : rawAbsent) if (fastMap.containsKey(key)) hits++;
            }
        } else {
            if (isSet) {
                for (Long key : absent) if (set.contains(key)) hits++;
            } else {
                for (Long key : absent) if (map.get(key) != null) hits++;
            }
        }
        return result = hits;
    }

    @Benchmark
    public long iterate() {
        long sum = 0;
        if (isFastutil) {
            if (isSet) {
                for (var it = fastSet.iterator(); it.hasNext(); ) sum += it.nextLong();
            } else {
                for (var it = fastMap.values().iterator(); it.hasNext(); ) sum += it.nextLong();
            }
        } else {
            if (isSet) {
                for (Long key : set) sum += key;
            } else {
                for (var entry : map.entrySet()) sum += entry.getValue();
            }
        }
        return result = sum;
    }

    @Benchmark
    public long remove() {
        long removed = 0;
        if (isFastutil) {
            if (isSet) {
                for (long key : rawRemoval) if (fastSet.remove(key)) removed++;
            } else {
                for (long key : rawRemoval) if (fastMap.remove(key) != fastMap.defaultReturnValue()) removed++;
            }
        } else {
            if (isSet) {
                for (Long key : removal) if (set.remove(key)) removed++;
            } else {
                for (Long key : removal) if (map.remove(key) != null) removed++;
            }
        }
        return result = removed;
    }

    @TearDown(Level.Iteration)
    public void verify() {
        switch (phase) {
            case "insert" -> { check(result == size); validate(); }
            case "remove" -> {
                check(result == size);
                check(isFastutil ? (isSet ? fastSet.isEmpty() : fastMap.isEmpty()) : (isSet ? set.isEmpty() : map.isEmpty()));
            }
            case "miss" -> check(result == 0);
            case "hit" -> check(result == (long) size * size);
            case "iterate" -> check(result == (isSet ? (long) size * (size - 1) : (long) size * size));
            default -> throw new IllegalStateException("Unknown phase");
        }
    }

    public static void main(String[] args) throws Exception {
        String[] implementations = {"tree_map", "tree_set", "fastutil_avl_map", "fastutil_avl_set", "fastutil_rb_map", "fastutil_rb_set"};
        for (String impl : implementations) {
            CollectionsBench bench = new CollectionsBench();
            bench.implementation = impl;
            bench.fixture = args[0];
            bench.load();
            for (String phase : new String[]{"insert", "hit", "miss", "iterate", "remove"}) {
                bench.preparePhase(phase);
                switch (phase) {
                    case "insert" -> bench.insert();
                    case "hit" -> bench.hit();
                    case "miss" -> bench.miss();
                    case "iterate" -> bench.iterate();
                    case "remove" -> bench.remove();
                }
                bench.verify();
            }
        }
    }
}
