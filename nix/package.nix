{
  lib,
  python313Packages,
  fetchFromGitHub,
}:
python313Packages.buildPythonApplication rec {
  pname = "phantom";
  version = "0.1.0";
  format = "pyproject";

  src = ../.;

  nativeBuildInputs = with python313Packages; [
    hatchling
  ];

  propagatedBuildInputs = with python313Packages; [
    # Core
    pydantic
    rich
    typer

    # Data processing
    pandas
    numpy
    polars

    # NLP & ML
    sentence-transformers
    transformers
    tiktoken
    nltk
    scikit-learn

    # Vector DB
    faiss
    chromadb

    # HTTP & API
    requests
    httpx
    fastapi
    uvicorn

    # Utilities
    python-magic
    pyyaml
    psutil
    aiofiles
  ];

  pythonImportsCheck = ["phantom"];

  meta = with lib; {
    description = "AI-Powered Document Intelligence & Classification Pipeline";
    homepage = "https://github.com/VoidNxSEC/phantom";
    license = licenses.asl20;
    maintainers = [];
    mainProgram = "phantom";
  };
}
