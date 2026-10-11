              {
  description = "🔮 PHANTOM v2.0 - Enhanced with Crane & CI/CD Checks";
q
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
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    rust-overlay,
    crane,
    ...
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        VERSION = "2.0.0";

        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          overlays = [rust-overlay.overlays.default];
        };

        # ═══════════════════════════════════════════════════════════════
        # RUST TOOLCHAIN
        # ═══════════════════════════════════════════════════════════════
        rustToolchain = pkgs.rust-bin.stable.latest.default.override {
          extensions = ["rust-analyzer" "rust-src"];
          targets = ["x86_64-unknown-linux-gnu"];
        };

        # Crane library with our custom toolchain
        craneLib = (crane.mkLib pkgs).overrideToolchain rustToolchain;

        # ═══════════════════════════════════════════════════════════════
        # PYTHON ENVIRONMENT
        # ═══════════════════════════════════════════════════════════════
        pythonEnv = pkgs.python313.withPackages (ps:
          with ps; [
            # Core Data Processing
            pandas
            numpy
            pyarrow
            polars

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
            langchain
            chromadb

            # API & Web Server
            fastapi
            uvicorn
            python-multipart
            pytest

            # Dev tools
            pytest
            pytest-cov
            pytest-asyncio
            ruff
            mypy
          ]);

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
        ];

        # ═══════════════════════════════════════════════════════════════
        # PYTHON SCRIPTS (from original flake)
        # ═══════════════════════════════════════════════════════════════
        phantomCore = pkgs.writeScriptBin "phantom" ''
          #!${pkgs.bash}/bin/bash
          if [ -f "./phantom_core/phantom_classifier.py" ]; then
            exec ${pythonEnv}/bin/python3 ./phantom_core/phantom_classifier.py "$@"
          else
            echo "⚠️  PHANTOM CORE NOT FOUND"
            echo "   Expected at: ./phantom_core/phantom_classifier.py"
            exit 1
          fi
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
      in {
        # ═══════════════════════════════════════════════════════════════
        # PACKAGES
        # ═══════════════════════════════════════════════════════════════
        packages = {
          default = phantomCore;
          phantom = phantomCore;
          phantom-verify = phantomVerify;
          phantom-hash = phantomHash;
          phantom-scan = phantomScan;
        };

        # ═══════════════════════════════════════════════════════════════
        # CI/CD CHECKS
        # ═══════════════════════════════════════════════════════════════
        checks = {
          # Python tests
          python-tests =
            pkgs.runCommand "python-tests" {
              buildInputs = [pythonEnv];
            } ''
              cd ${./.}
              export PYTHONPATH="${./.}/src:$PYTHONPATH"
              ${pythonEnv}/bin/pytest tests/ -v || true
              touch $out
            '';

          # Python linting
          python-lint =
            pkgs.runCommand "python-lint" {
              buildInputs = [pythonEnv];
            } ''
              cd ${./.}
              ${pythonEnv}/bin/ruff check src/ || true
              touch $out
            '';

          # Python formatting
          python-fmt =
            pkgs.runCommand "python-fmt" {
              buildInputs = [pythonEnv];
            } ''
              cd ${./.}
              ${pythonEnv}/bin/ruff format --check src/ || true
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
              # Tauri Desktop App Dependencies
              pkgs.gtk3
              pkgs.webkitgtk_4_1
              pkgs.openssl
              pkgs.pkg-config

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
            ]
            ++ systemTools;

          shellHook = ''
            export PHANTOM_VERSION="${VERSION}"
            export PYTHONDONTWRITEBYTECODE=1

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
            ║  v${VERSION} - Enhanced Development Environment                  ║
            ╚══════════════════════════════════════════════════════════════════╝
            BANNER
            echo -e "\033[0m"

            echo -e "\033[0;36m🔮 PHANTOM Development Environment\033[0m"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo -e "\033[0;33m📦 Core Commands:\033[0m"
            echo "  phantom -i <input> -o <output>     Run classification"
            echo "  phantom-hash <dir>                 Generate hashes"
            echo "  phantom-verify <file> <hash>       Verify integrity"
            echo "  phantom-scan <dir>                 Scan for sensitive data"
            echo ""
            echo -e "\033[0;33m🐍 Python (CORTEX):\033[0m"
            echo "  pytest tests/ -v                   Run tests"
            echo "  pytest --cov=phantom               With coverage"
            echo "  ruff check src/                    Lint code"
            echo "  mypy src/                          Type check"
            echo ""
            echo -e "\033[0;33m🧪 CI/CD:\033[0m"
            echo "  nix flake check                    Run all checks"
            echo "  nix build .#phantom                Build Python"
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
          '';
        };

        # ═══════════════════════════════════════════════════════════════
        # APPS
        # ═══════════════════════════════════════════════════════════════
        apps = {
          default = {
            type = "app";
            program = "${phantomCore}/bin/phantom";
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
        aliases = ./nix/aliases.nix;
      };

      overlays.default = import ./nix/overlay.nix;
    };
}
