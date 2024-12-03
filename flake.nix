{
  inputs = {
    flake-compat = {
      url = "github:edolstra/flake-compat";
    };

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs = {
        nixpkgs-lib.follows = "nixpkgs";
      };
    };

    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs = {
        flake-compat.follows = "flake-compat";
        nixpkgs-stable.follows = "nixpkgs";
        nixpkgs.follows = "nixpkgs";
      };
    };

    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    pyproject-nix = {
      url = "github:nix-community/pyproject.nix";
      inputs = {
        nixpkgs.follows = "nixpkgs";
      };
    };

    uv2nix = {
      url = "github:adisbladis/uv2nix";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        pyproject-nix.follows = "pyproject-nix";
      };
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        nixpkgs.follows = "nixpkgs";
      };
    };

    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs = {
        nixpkgs.follows = "nixpkgs";
      };
    };
  };

  outputs =
    inputs@{
      self,
      flake-parts,
      treefmt-nix,
      ...
    }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        treefmt-nix.flakeModule
      ];

      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];

      perSystem =
        {
          config,
          lib,
          pkgs,
          system,
          ...
        }:
        {
          checks = {
            git-hooks-check = inputs.git-hooks.lib.${system}.run {
              src = ./.;
              hooks.treefmt = {
                enable = true;
                package = config.treefmt.build.wrapper;
              };
            };
          };

          devShells.default =
            let
              workspace = inputs.uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
              overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
              python = pkgs.python312;
              pyprojectOverrides = _final: _prev: { };
              pythonSet =
                (pkgs.callPackage inputs.pyproject-nix.build.packages { inherit python; }).overrideScope
                  (
                    pkgs.lib.composeManyExtensions [
                      inputs.pyproject-build-systems.overlays.default
                      overlay
                      pyprojectOverrides
                    ]
                  );
              editableOverlay = workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; };
              editablePythonSet = pythonSet.overrideScope editableOverlay;
              virtualenv = editablePythonSet.mkVirtualEnv "grafana-sync-dev-env" {
                grafana-sync = [ "test" ];
              };
            in
            pkgs.mkShell {
              packages = [
                virtualenv
                pkgs.pyright
                pkgs.uv
              ];
              shellHook = ''
                # Undo dependency propagation by nixpkgs.
                unset PYTHONPATH

                # Get repository root using git. This is expanded at runtime by the editable `.pth` machinery.
                export REPO_ROOT=$(git rev-parse --show-toplevel)

                # venv managed via uv2nix
                export UV_NO_SYNC=1

                # Ensure .venv symlink exists and points to the current venv
                if [ ! -L "$REPO_ROOT/.venv" ] || [ "$(readlink "$REPO_ROOT/.venv")" != "${virtualenv}" ]; then
                  ln -sfn "${virtualenv}" "$REPO_ROOT/.venv"
                fi

                ${self.checks.${system}.git-hooks-check.shellHook}
              '';
            };

          treefmt.config = {
            flakeCheck = true;
            programs.deadnix.enable = true;
            programs.nixfmt.enable = true;
            programs.ruff = {
              check = true;
              format = true;
            };
          };
        };
    };
}
