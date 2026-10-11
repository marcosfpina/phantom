{
  lib,
  python314Packages,
  fetchFromGitHub,
}:
python314Packages.buildPythonApplication rec {
  pname = "phantom";
  version = "0.1.0";
  format = "pyproject";

  src = ../.;

  nativeBuildInputs = with python314Packages; [
    hatchling
  ];

  propagatedBuildInputs = with python314Packages; [
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
    homepage = "https://github.com/marcosfpina/phantom";
    license = licenses.asl20;
    maintainers = [ marcosfpina ];
    mainProgram = "phantom";
  };
}
