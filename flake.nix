{
  description = "A flake for the flyingcircus batou_ext library";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

    treefmt-nix.url = "github:numtide/treefmt-nix";
    nix-filter.url = "github:numtide/nix-filter";

    batou.url = "github:flyingcircusio/batou/phil/flakify-batou";
    batou.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = inputs @ {flake-parts, ...}:
    flake-parts.lib.mkFlake {inherit inputs;} {
      imports = [
        inputs.treefmt-nix.flakeModule
      ];

      systems = [
        "x86_64-linux"
        "aarch64-darwin"
      ];

      perSystem = {
        config,
        pkgs,
        inputs',
        ...
      }: let
        src = inputs.nix-filter.lib {
          root = inputs.self;
          exclude = [
            (inputs.nix-filter.lib.matchExt "nix")
            "flake.lock"
          ];
        };
        batou_ext = pkgs.python3Packages.callPackage ./nix/batou_ext.nix {
          inherit src;
          inherit (inputs'.batou.packages) batou;
        };
      in {
        treefmt = {
          projectRootFile = "flake.nix";
          programs.alejandra.enable = true;
          settings.formatter.alejandra.excludes = [
            "src/batou_ext/*"
          ];
          flakeCheck = false;
        };

        formatter = config.treefmt.build.wrapper;

        packages = rec {
          default = batou_ext;
          inherit batou_ext;
        };

        checks = {
          inherit batou_ext;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: [batou_ext ps.tox]))
          ];

          shellHook = ''
            export APPENV_BASEDIR=$PWD
          '';
        };
      };
    };
}
