$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install ".[dev,http]"
ruff check .
ruff format --check .
mypy src
pytest --cov-report=xml
python -m build
python -m twine check dist/*
pyinstaller --clean --onefile --name autoscreenrec src/automated_screen_recorder/cli.py
