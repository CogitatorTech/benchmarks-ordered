package bench;

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
    @Param({"tree_map", "tree_set"})
    public String implementation;
    @Param({"fixture.bin"})
    public String fixture;
    private boolean isSet;
    private int size;
    private Long[] insertion, values, lookup, absent, removal;
    private TreeMap<Long, Long> map;
    private TreeSet<Long> set;
    private String phase;
    private long result;

    private static void check(boolean ok) {
        if (!ok) throw new IllegalStateException("Benchmark mismatch");
    }

    @Setup(Level.Trial)
    public void load() throws IOException {
        check(implementation.equals("tree_set") || implementation.equals("tree_map"));
        isSet = implementation.equals("tree_set");
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
        for (int i = 0; i < size; i++) {
            insertion[i] = readKey(data);
            values[i] = insertion[i] + 1;
        }
        for (int i = 0; i < size; i++) {
            lookup[i] = readKey(data);
            absent[i] = lookup[i] + 1;
        }
        for (int i = 0; i < size; i++) removal[i] = readKey(data);
        fresh();
        populate();
        validate();
        if (size > 0) {
            if (isSet) {
                set.add(0L);
                check(set.size() == size);
            } else {
                map.put(0L, -1L);
                check(map.size() == size && map.get(0L) == -1L);
                map.put(0L, 1L);
            }
        }
        check(isSet ? !set.remove(-1L) : map.remove(-1L) == null);
    }

    private long readKey(ByteBuffer data) {
        long key = data.getLong();
        check(key >= 0 && key < size * 2L && key % 2 == 0);
        return key;
    }

    private void fresh() {
        if (isSet) set = new TreeSet<>();
        else map = new TreeMap<>();
    }

    private void populate() {
        if (isSet) {
            for (Long key : insertion) set.add(key);
        } else {
            for (int i = 0; i < size; i++) map.put(insertion[i], values[i]);
        }
    }

    private void validate() {
        check(isSet ? set.size() == size : map.size() == size);
        long index = 0;
        if (isSet) {
            for (Long key : set) check(key == index++ * 2);
        } else {
            for (var entry : map.entrySet()) {
                check(entry.getKey() == index++ * 2);
                check(entry.getValue() == entry.getKey() + 1);
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
        return result = isSet ? set.size() : map.size();
    }

    @Benchmark
    public long hit() {
        long sum = 0;
        if (isSet) {
            for (Long key : lookup) if (set.contains(key)) sum += key + 1;
        } else {
            for (Long key : lookup) {
                Long value = map.get(key);
                if (value != null) sum += value;
            }
        }
        return result = sum;
    }

    @Benchmark
    public long miss() {
        long hits = 0;
        if (isSet) {
            for (Long key : absent) if (set.contains(key)) hits++;
        } else {
            for (Long key : absent) if (map.get(key) != null) hits++;
        }
        return result = hits;
    }

    @Benchmark
    public long iterate() {
        long sum = 0;
        if (isSet) {
            for (Long key : set) sum += key;
        } else {
            for (var entry : map.entrySet()) sum += entry.getValue();
        }
        return result = sum;
    }

    @Benchmark
    public long remove() {
        long removed = 0;
        if (isSet) {
            for (Long key : removal) if (set.remove(key)) removed++;
        } else {
            for (Long key : removal) if (map.remove(key) != null) removed++;
        }
        return result = removed;
    }

    @TearDown(Level.Iteration)
    public void verify() {
        switch (phase) {
            case "insert" -> { check(result == size); validate(); }
            case "remove" -> {
                check(result == size);
                check(isSet ? set.isEmpty() : map.isEmpty());
            }
            case "miss" -> check(result == 0);
            case "hit" -> check(result == (long) size * size);
            case "iterate" -> check(result == (isSet ? (long) size * (size - 1) : (long) size * size));
            default -> throw new IllegalStateException("Unknown phase");
        }
    }

    public static void main(String[] args) throws Exception {
        for (String impl : new String[]{"tree_map", "tree_set"}) {
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
