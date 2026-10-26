{
  description = "Benchmarks for the Ordered Library";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    zig-overlay.url = "github:mitchellh/zig-overlay";
    zig-overlay.inputs.nixpkgs.follows = "nixpkgs";
    rust-overlay.url = "github:oxalica/rust-overlay";
    rust-overlay.inputs.nixpkgs.follows = "nixpkgs";
    ordered = {
      url = "github:CogitatorTech/ordered/864d82da5cc060e668cb4fb9c0de5450fcf47985";
      flake = false;
    };
    klib = {
      url = "github:attractivechaos/klib";
      flake = false;
    };
  };

  outputs =
    {
      nixpkgs,
      zig-overlay,
      rust-overlay,
      ordered,
      klib,
      ...
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
    in
    {
      devShells = nixpkgs.lib.genAttrs systems (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ rust-overlay.overlays.default ];
          };
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              zig-overlay.packages.${system}."0.17.0"
              gcc
              git
              (rust-bin.fromRustupToolchainFile ./rust-toolchain.toml)
              jdk25
              (maven.override { jdk_headless = jdk25; })
              python315
              uv
              gnumake
              cmake
              ninja
              abseil-cpp
              nixfmt
            ];
            ORDERED_SOURCE = "${ordered}";
            KLIB_SOURCE = "${klib}";
            ABSEIL_PREFIX = "${pkgs.abseil-cpp.dev}";
          };
        }
      );
    };
}
