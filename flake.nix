{
  description = "Phantom - Document Intelligence Engine";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    # Rust toolchain overlay
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Crane for incremental Rust builds
    crane = {
      url = "github:ipetkov/crane";
    };

    advisory-db = {
      url = "github:rustsec/advisory-db";
      #flake = true;
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    rust-overlay,
    crane,
    advisory-db,
    ...
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        VERSION = "0.1.0";

        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          overlays = [rust-overlay.overlays.default];
        };

        # ═══════════════════════════════════════════════════════════════
        # RUST TOOLCHAIN
        # ═══════════════════════════════════════════════════════════════
        rustToolchain = pkgs.rust-bin.stable.latest.default.override {
          extensions = [
            "rust-analyzer"
            "rust-src"
          ];
          targets = ["x86_64-unknown-linux-gnu"];
        };

        # Crane library with our custom toolchain
        craneLib = (crane.mkLib pkgs).overrideToolchain rustToolchain;

        # ═══════════════════════════════════════════════════════════════
        # PYTHON ENVIRONMENT
        # ═══════════════════════════════════════════════════════════════
        pythonEnv = pkgs.python313.withPackages (
          ps:
            with ps; [
              # Core Data Processing
              numpy
              pyarrow

              # File Analysis
              python-magic
              chardet
              filetype

              # Hashing & Cryptography
              cryptography
              pynacl

              # NLP & Classification
              nltk
              scikit-learn

              # Metadata & Forensics
              exifread
              pdfminer-six
              python-docx
              openpyxl

              # Serialization & Reporting
              pyyaml
              toml
              jinja2
              rich
              tqdm

              # Native GTK4 desktop
              pygobject3
              pycairo

              # HTTP & Networking
              requests

              # System Monitoring
              psutil

              # Async & Parallelism
              aiofiles
              multiprocess

              # Validation
              jsonschema
              pydantic

              # CORTEX v2.0: Embeddings & Chunking
              sentence-transformers
              transformers
              torch
              tiktoken
              faiss

              # API & Web Server
              fastapi
              uvicorn
              python-multipart
              httpx

              # Observability & Logging
              prometheus-client
              structlog

              # CLI
              typer

              # Dev tools
              pytest
              pytest-cov
              pytest-asyncio
              ruff
              mypy
            ]
        );

        # ═══════════════════════════════════════════════════════════════
        # SYSTEM TOOLS
        # ═══════════════════════════════════════════════════════════════
        systemTools = with pkgs; [
          # Data Manipulation
          jq
          yq-go
          miller
          gron
          htmlq

          nodejs
          bun

          # File Analysis
          file
          exiftool
          binwalk
          hexyl

          # Hashing & Integrity
          b3sum
          xxHash
          rhash

          # Search & Discovery
          ripgrep
          fd
          fzf
          tree

          # Compression & Archive
          p7zip
          unzip
          gzip
          xz
          zstd

          # Security & Forensics
          foremost
          sleuthkit

          # Monitoring
          pv
          parallel
          just

          # Documentation
          doxygen
          graphviz
        ];

        # ═══════════════════════════════════════════════════════════════
        # LEGACY RUST BUILD CONFIGURATION (Cortex Desktop / Tauri)
        # ═══════════════════════════════════════════════════════════════

        # Source filtering - include Tauri-specific files
        src = pkgs.lib.cleanSourceWith {
          src = ./cortex-desktop/src-tauri;
          name = "cortex-desktop-source";
          filter = path: type: let
            baseName = baseNameOf path;
          in
            # Include all Cargo standard files
            (craneLib.filterCargoSources path type)
            # Include all JSON files (tauri.conf.json, capabilities/*.json)
            || (pkgs.lib.hasSuffix ".json" baseName)
            # Include all image files (icons)
            || (pkgs.lib.hasSuffix ".png" baseName)
            || (pkgs.lib.hasSuffix ".ico" baseName)
            || (pkgs.lib.hasSuffix ".icns" baseName);
        };

        # Common arguments for all Crane builds
        commonArgs = {
          inherit src;

          # Native build inputs
          nativeBuildInputs = with pkgs; [
            pkg-config
          ];

          # Build inputs (libraries)
          buildInputs = with pkgs; [
            openssl
            gtk4
            libadwaita
            webkitgtk_4_1
          ];

          # Environment variables
          CARGO_BUILD_INCREMENTAL = "true";
        };

        # Build dependencies only (cached separately)
        cargoArtifacts = craneLib.buildDepsOnly (
          commonArgs
          // {
            pname = "cortex-desktop-deps";
          }
        );

        # Build the actual workspace
        cortexDesktop = craneLib.buildPackage (
          commonArgs
          // {
            inherit cargoArtifacts;
            pname = "cortex-desktop";
            version = VERSION;

            # Don't run tests in build (we do that separately)
            doCheck = false;
          }
        );

        # ═══════════════════════════════════════════════════════════════
        # PYTHON SCRIPTS (from original flake)
        # ═══════════════════════════════════════════════════════════════
        phantomCore = pkgs.writeScriptBin "phantom" ''
          #!${pkgs.bash}/bin/bash
          export PYTHONPATH=$PYTHONPATH:${./.}/src
          exec ${pythonEnv}/bin/python3 -m phantom.cli.main "$@"
        '';

        phantomVerify = pkgs.writeScriptBin "phantom-verify" ''
          #!/usr/bin/env bash
          set -euo pipefail

          if [[ $# -lt 2 ]]; then
            echo "Usage: phantom-verify <file> <expected_sha256>"
            exit 1
          fi

          FILE="$1"
          EXPECTED="$2"
          ACTUAL=$(sha256sum "$FILE" | cut -d' ' -f1)

          if [[ "$ACTUAL" == "$EXPECTED" ]]; then
            echo -e "\033[0;32m✓ INTEGRITY OK: $FILE\033[0m"
            exit 0
          else
            echo -e "\033[0;31m✗ INTEGRITY FAILURE: $FILE\033[0m"
            echo "  Expected: $EXPECTED"
            echo "  Got:      $ACTUAL"
            echo -e "\033[0;31m✗ INTEGRITY FAILURE: $FILE\033[0m"
            exit 1
          fi
        '';

        phantomHash = pkgs.writeScriptBin "phantom-hash" ''
          #!/usr/bin/env bash
          set -euo pipefail

          DIR="''${1:-.}"
          OUTPUT="''${2:-manifest.json}"

          echo "{"
          echo '  "generated": "'$(date -Iseconds)'",'
          echo '  "files": ['

          FIRST=true
          find "$DIR" -type f -print0 | while IFS= read -r -d "" file; do
            SHA=$(sha256sum "$file" | cut -d' ' -f1)
            B3=$(b3sum --no-names "$file" 2>/dev/null || echo "N/A")
            SIZE=$(stat -c%s "$file")

            if [[ "$FIRST" != true ]]; then
              echo ","
            fi
            FIRST=false

            printf '    {"path": "%s", "sha256": "%s", "blake3": "%s", "size": %d}' \
              "$file" "$SHA" "$B3" "$SIZE"
          done

          echo ""
          echo "  ]"
          echo "}"
        '';

        phantomScan = pkgs.writeScriptBin "phantom-scan" ''
          #!/usr/bin/env bash
          set -euo pipefail

          DIR="''${1:-.}"

          echo -e "\033[0;35m🔍 PHANTOM SENSITIVE SCANNER\033[0m"
          echo "==============================="

          # Email patterns
          echo -e "\n\033[0;33m📧 Email addresses:\033[0m"
          rg -oIN '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}' "$DIR" 2>/dev/null | head -20 || echo "  None found"

          # IP addresses
          echo -e "\n\033[0;33m🌐 IP addresses:\033[0m"
          rg -oIN '\b(?:\d{1,3}\.){3}\d{1,3}\b' "$DIR" 2>/dev/null | head -20 || echo "  None found"

          # Potential credentials
          echo -e "\n\033[0;33m🔑 Potential credentials:\033[0m"
          rg -iIN '(password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*["\x27]?[^\s"\x27]+' "$DIR" 2>/dev/null | head -20 || echo "  None found"

          # Private keys
          echo -e "\n\033[0;33m🔐 Private keys:\033[0m"
          rg -lIN '-----BEGIN.*PRIVATE KEY-----' "$DIR" 2>/dev/null || echo "  None found"

          echo -e "\n\033[0;32m✓ Scan complete\033[0m"
        '';

        phantomApi = pkgs.writeScriptBin "phantom-api" ''
          #!${pkgs.bash}/bin/bash
          export PYTHONPATH=$PYTHONPATH:${./.}/src
          exec ${pythonEnv}/bin/python3 ${./.}/src/phantom/api/app.py "$@"
        '';

        phantomDesktopDev = pkgs.writeScriptBin "phantom-desktop" ''
          #!${pkgs.bash}/bin/bash
          REPO_ROOT="''${PHANTOM_REPO_ROOT:-$(pwd)}"
          export PYTHONPATH="$REPO_ROOT/src:''${PYTHONPATH:-}"
          exec ${pythonEnv}/bin/python3 "$REPO_ROOT/apps/desktop/main.py" "$@"
        '';

        phantomDesktop = pkgs.callPackage ./nix/desktop.nix {};
      in {
        # ═══════════════════════════════════════════════════════════════
        # PACKAGES
        # ═══════════════════════════════════════════════════════════════
        packages = {
          default = phantomDesktop;
          phantom = phantomCore;
          phantomDesktop = phantomDesktop;
          phantom-desktop = phantomDesktop;
          phantom-verify = phantomVerify;
          phantom-hash = phantomHash;
          phantom-scan = phantomScan;
          phantom-api = phantomApi;
          cortexDesktopLegacy = cortexDesktop;
        };

        formatter = pkgs.alejandra;

        # ═══════════════════════════════════════════════════════════════
        # CI/CD CHECKS
        # ═══════════════════════════════════════════════════════════════
        checks = {
          # Python tests
          python-tests =
            pkgs.runCommand "python-tests"
            {
              buildInputs = [pythonEnv];
            }
            ''
              cd ${./.}
              export PYTHONPATH="${./.}/src:$PYTHONPATH"
              ${pythonEnv}/bin/pytest tests/ -v
              touch $out
            '';

          # Python linting
          python-lint =
            pkgs.runCommand "python-lint"
            {
              buildInputs = [pythonEnv];
            }
            ''
              cd ${./.}
              ${pythonEnv}/bin/ruff check src/
              touch $out
            '';

          # Python formatting
          python-fmt =
            pkgs.runCommand "python-fmt"
            {
              buildInputs = [pythonEnv];
            }
            ''
              cd ${./.}
              ${pythonEnv}/bin/ruff format --check src/
              touch $out
            '';
        };

        # ═══════════════════════════════════════════════════════════════
        # DEVELOPMENT SHELL
        # ═══════════════════════════════════════════════════════════════
        devShells.default = pkgs.mkShell {
          name = "phantom-dev";

          buildInputs =
            [
              # GTK4 desktop app dependencies
              pkgs.openssl
              pkgs.pkg-config
              pkgs.gtk4
              pkgs.libadwaita
              pkgs.glib
              pkgs.gobject-introspection
              pkgs.gsettings-desktop-schemas

              # Rust Toolchain
              rustToolchain
              pkgs.cargo-watch
              pkgs.cargo-nextest
              pkgs.cargo-audit
              pkgs.cargo-outdated

              # Python environment
              pythonEnv

              # Phantom scripts
              phantomCore
              phantomVerify
              phantomHash
              phantomScan
              phantomApi
              phantomDesktopDev
            ]
            ++ systemTools;

          shellHook = ''
            export PHANTOM_VERSION="${VERSION}"
            export PHANTOM_REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
            export PYTHONDONTWRITEBYTECODE=1
            export PYTHONPATH="$PHANTOM_REPO_ROOT/src:$PYTHONPATH"

            # Rust environment
            export RUST_BACKTRACE=1
            export RUST_LOG=info

            # Create work directories
            mkdir -p .phantom/{input,output,staging,quarantine}

            echo -e "\033[0;35m"
            cat << 'BANNER'
            ╔══════════════════════════════════════════════════════════════════╗
            ║  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗ ║
            ║  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║ ║
            ║  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║ ║
            ║  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║ ║
            ║  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║ ║
            ║  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝ ║
            ║  v0.1.0 - SOVEREIGN MONOREPO | LOCAL-FIRST AI                    ║
            ╚══════════════════════════════════════════════════════════════════╝
            BANNER
            echo -e "\033[0m"

            echo -e "\033[1;36m🔮 PROJECT STATUS: Writer Sandbox Expansion (v${VERSION})\033[0m"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo -e "  🔹 \033[1mPHANTOM CORE:\033[0m  Python 3.13, FastAPI, CORTEX V2.0"
            echo -e "  🔹 \033[1mWRITER GUI:\033[0m     GTK4/libadwaita, local Markdown"
            echo -e "  🔹 \033[1mENVIRONMENT:\033[0m   Hermetic Nix Shell, Crane-backed builds"
            echo ""

            echo -e "\033[1;33m🚀 QUICK ACTIONS\033[0m"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo -e "  \033[1mjust serve\033[0m        Start API server (8008)"
            echo -e "  \033[1mjust desktop\033[0m      Launch Desktop GUI"
            echo -e "  \033[1mjust test\033[0m         Run full test suite"
            echo -e "  \033[1mjust lint\033[0m         Check code quality (ruff/mypy)"
            echo ""

            echo -e "\033[1;35m🛠️  PHANTOM TOOLKIT\033[0m"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo -e "  \033[1mphantom-api\033[0m       Direct API interactions"
            echo -e "  \033[1mphantom-scan\033[0m      PII & Secret scanner"
            echo -e "  \033[1mphantom-hash\033[0m      Cryptographic manifest generator"
            echo ""
            echo -e "\033[0;90m📚 DOCUMENTATION: ./docs\033[0m"
            echo -e "\033[0;90mType 'just --list' for all available automation tasks.\033[0m"
            echo ""
          '';
        };

        # ═══════════════════════════════════════════════════════════════
        # APPS
        # ═══════════════════════════════════════════════════════════════
        apps = {
          default = {
            type = "app";
            program = "${phantomDesktop}/bin/phantom-desktop";
          };
          phantomDesktop = {
            type = "app";
            program = "${phantomDesktop}/bin/phantom-desktop";
          };
          cortexDesktopLegacy = {
            type = "app";
            program = "${cortexDesktop}/bin/cortex-desktop";
          };
          phantom = {
            type = "app";
            program = "${phantomCore}/bin/phantom";
          };
        };
      }
    )
    // {
      # ═══════════════════════════════════════════════════════════════
      # NIXOS MODULES (system-wide)
      # ═══════════════════════════════════════════════════════════════
      nixosModules = {
        default = ./nix/module.nix;
        phantom = ./nix/module.nix;
        desktop = ./nix/desktop.nix;
        aliases = ./nix/aliases.nix;
        package = ./nix/package.nix;
      };

      overlays.default = import ./nix/overlay.nix;
    };
}
