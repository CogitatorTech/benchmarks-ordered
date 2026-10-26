const std = @import("std");

pub fn build(b: *std.Build) !void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const ordered = if (b.option([]const u8, "ordered", "Override the Ordered source directory")) |source|
        b.createModule(.{
            .root_source_file = .{ .cwd_relative = b.pathJoin(&.{ source, "src/lib.zig" }) },
            .target = target,
            .optimize = optimize,
        })
    else
        (try b.dependencyLazy("ordered", .{ .target = target, .optimize = optimize })).module("ordered");
    const module = b.createModule(.{
        .root_source_file = b.path("benchmarks/zig/main.zig"),
        .target = target,
        .optimize = optimize,
        .link_libc = true,
    });
    module.addImport("ordered", ordered);
    b.installArtifact(b.addExecutable(.{ .name = "zig-bench", .root_module = module }));
}
