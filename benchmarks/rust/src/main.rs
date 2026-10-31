use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::time::Instant;

trait Collection: Default {
    const IS_SET: bool;
    fn put(&mut self, key: i64, value: i64);
    fn get(&self, key: i64) -> Option<i64>;
    fn remove(&mut self, key: i64) -> bool;
    fn len(&self) -> usize;
    fn sum(&self) -> i64;
    fn validate(&self);
}
impl Collection for BTreeMap<i64, i64> {
    const IS_SET: bool = false;
    fn put(&mut self, k: i64, v: i64) {
        self.insert(k, v);
    }
    fn get(&self, k: i64) -> Option<i64> {
        BTreeMap::get(self, &k).copied()
    }
    fn remove(&mut self, k: i64) -> bool {
        BTreeMap::remove(self, &k).is_some()
    }
    fn len(&self) -> usize {
        BTreeMap::len(self)
    }
    fn sum(&self) -> i64 {
        self.values().sum()
    }
    fn validate(&self) {
        for (i, (&k, &v)) in self.iter().enumerate() {
            assert_eq!((k, v), (i as i64 * 2, i as i64 * 2 + 1));
        }
    }
}
impl Collection for BTreeSet<i64> {
    const IS_SET: bool = true;
    fn put(&mut self, k: i64, _: i64) {
        self.insert(k);
    }
    fn get(&self, k: i64) -> Option<i64> {
        BTreeSet::get(self, &k).copied()
    }
    fn remove(&mut self, k: i64) -> bool {
        BTreeSet::remove(self, &k)
    }
    fn len(&self) -> usize {
        BTreeSet::len(self)
    }
    fn sum(&self) -> i64 {
        self.iter().sum()
    }
    fn validate(&self) {
        for (i, &k) in self.iter().enumerate() {
            assert_eq!(k, i as i64 * 2);
        }
    }
}
impl Collection for indexset::BTreeMap<i64, i64> {
    const IS_SET: bool = false;
    fn put(&mut self, k: i64, v: i64) {
        self.insert(k, v);
    }
    fn get(&self, k: i64) -> Option<i64> {
        indexset::BTreeMap::get(self, &k).copied()
    }
    fn remove(&mut self, k: i64) -> bool {
        indexset::BTreeMap::remove(self, &k).is_some()
    }
    fn len(&self) -> usize {
        indexset::BTreeMap::len(self)
    }
    fn sum(&self) -> i64 {
        self.values().sum()
    }
    fn validate(&self) {
        for (i, (&k, &v)) in self.iter().enumerate() {
            assert_eq!((k, v), (i as i64 * 2, i as i64 * 2 + 1));
        }
    }
}
impl Collection for indexset::BTreeSet<i64> {
    const IS_SET: bool = true;
    fn put(&mut self, k: i64, _: i64) {
        self.insert(k);
    }
    fn get(&self, k: i64) -> Option<i64> {
        if self.contains(&k) { Some(k) } else { None }
    }
    fn remove(&mut self, k: i64) -> bool {
        indexset::BTreeSet::remove(self, &k)
    }
    fn len(&self) -> usize {
        indexset::BTreeSet::len(self)
    }
    fn sum(&self) -> i64 {
        self.iter().sum()
    }
    fn validate(&self) {
        for (i, &k) in self.iter().enumerate() {
            assert_eq!(k, i as i64 * 2);
        }
    }
}

fn fresh<C: Collection>(keys: &[i64], n: usize) -> C {
    let mut c = C::default();
    for &key in &keys[..n] {
        c.put(key, key + 1);
    }
    assert_eq!(c.len(), n);
    c.validate();
    c
}

fn measure<C: Collection>(keys: &[i64], n: usize, emit: bool) {
    let mut c = C::default();
    let mut times = [0u128; 5];
    let start = Instant::now();
    for &k in &keys[..n] {
        c.put(k, k + 1);
    }
    times[0] = start.elapsed().as_nanos();
    assert_eq!(c.len(), n);
    c.validate();
    if n > 0 {
        c.put(0, -1);
        assert_eq!(c.get(0), Some(if C::IS_SET { 0 } else { -1 }));
        c.put(0, 1);
        assert_eq!(c.len(), n);
    }
    assert!(!c.remove(-1));
    let expected = if C::IS_SET {
        n as i64 * (n as i64 - 1)
    } else {
        (n * n) as i64
    };
    drop(c);
    c = fresh::<C>(keys, n);
    let start = Instant::now();
    let sum: i64 = keys[n..n * 2]
        .iter()
        .filter_map(|&k| c.get(k))
        .map(|v| v + i64::from(C::IS_SET))
        .sum();
    times[1] = start.elapsed().as_nanos();
    assert_eq!(sum, (n * n) as i64);
    drop(c);
    c = fresh::<C>(keys, n);
    let start = Instant::now();
    let misses = keys[n..n * 2]
        .iter()
        .filter(|&&k| c.get(k + 1).is_some())
        .count();
    times[2] = start.elapsed().as_nanos();
    assert_eq!(misses, 0);
    drop(c);
    c = fresh::<C>(keys, n);
    let start = Instant::now();
    let sum = c.sum();
    times[3] = start.elapsed().as_nanos();
    assert_eq!(sum, expected);
    drop(c);
    c = fresh::<C>(keys, n);
    let start = Instant::now();
    let removed = keys[n * 2..].iter().filter(|&&k| c.remove(k)).count();
    times[4] = start.elapsed().as_nanos();
    assert_eq!(removed, n);
    assert_eq!(c.len(), 0);
    if emit {
        for (phase, ns) in ["insert", "hit", "miss", "iterate", "remove"]
            .iter()
            .zip(times)
        {
            println!("{phase},{ns}");
        }
        println!();
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(args.len(), 5);
    let bytes = fs::read(&args[2]).expect("fixture read");
    assert!(bytes.len() >= 8);
    let n = u64::from_le_bytes(bytes[..8].try_into().unwrap()) as usize;
    assert!(n <= 10_000_000 && bytes.len() == 8 + n * 24);
    let keys: Vec<i64> = bytes[8..]
        .chunks_exact(8)
        .map(|b| i64::from_le_bytes(b.try_into().unwrap()))
        .collect();
    assert!(
        keys.iter()
            .all(|&k| k >= 0 && k < n as i64 * 2 && k % 2 == 0)
    );
    let warmups: usize = args[3].parse().unwrap();
    let samples: usize = args[4].parse().unwrap();
    assert!(warmups <= 1000 && samples > 0 && samples <= 1000);
    for i in 0..warmups + samples {
        match args[1].as_str() {
            "btree_map" => measure::<BTreeMap<i64, i64>>(&keys, n, i >= warmups),
            "btree_set" => measure::<BTreeSet<i64>>(&keys, n, i >= warmups),
            "indexset_map" => measure::<indexset::BTreeMap<i64, i64>>(&keys, n, i >= warmups),
            "indexset_set" => measure::<indexset::BTreeSet<i64>>(&keys, n, i >= warmups),
            _ => panic!("unknown implementation"),
        }
    }
}
