# Nix derivation for Phantom Desktop GTK4 application
{
  lib,
  python313Packages,
  gtk4,
  libadwaita,
  wrapGAppsHook4,
  gobject-introspection,
}:
python313Packages.buildPythonApplication rec {
  pname = "phantom-desktop";
  version = "0.1.0";
  format = "other"; # Not a standard Python package

  src = ./..;

  nativeBuildInputs = [
    wrapGAppsHook4
    gobject-introspection
  ];

  buildInputs = [
    gtk4
    libadwaita
  ];

  propagatedBuildInputs = with python313Packages; [
    pygobject3
    pycairo
    pydantic
    pyyaml
    rich
  ];

  # No build step - just install
  dontBuild = true;

  installPhase = ''
    mkdir -p $out/bin $out/share/applications $out/share/phantom

    # Copy the runtime source and main script
    cp -r src $out/share/phantom/src
    cp apps/desktop/main.py $out/share/phantom/phantom-desktop.py

    # Create launcher script
    cat > $out/bin/phantom-desktop << EOF
    #!/usr/bin/env bash
    export PYTHONPATH=$out/share/phantom/src:\''${PYTHONPATH:-}
    exec python3 $out/share/phantom/phantom-desktop.py "\$@"
    EOF
    chmod +x $out/bin/phantom-desktop

    # Desktop entry
    cat > $out/share/applications/dev.phantom.desktop.desktop << EOF
    [Desktop Entry]
    Name=Phantom Desktop
    Comment=AI-Powered Document Intelligence
    Exec=$out/bin/phantom-desktop
    Icon=utilities-system-monitor
    Type=Application
    Categories=Utility;Development;
    Terminal=false
    EOF
  '';

  meta = with lib; {
    description = "Phantom Desktop - Native GTK4 Document Intelligence";
    homepage = "https://github.com/VoidNxSEC/phantom";
    license = licenses.asl20;
    maintainers = [];
    mainProgram = "phantom-desktop";
    platforms = platforms.linux;
  };
}
