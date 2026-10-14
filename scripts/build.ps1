$ErrorActionPreference = "Stop"

Set-StrictMode -Version Latest

$ProjectRoot = Resolve-Path (
    Join-Path $PSScriptRoot ".."
)

Push-Location $ProjectRoot

try {
    Write-Host "==> Upgrading pip"
    python -m pip install --upgrade pip

    Write-Host "==> Installing current development dependencies"
    python -m pip install `
        --upgrade `
        -e ".[dev,http]"

    Write-Host "==> Installed packaging tool versions"
    python -m build --version
    python -m twine --version

    python -c `
        "from importlib.metadata import version; print('pkginfo:', version('pkginfo'))"

    python -c `
        "from importlib.metadata import version; print('hatchling:', version('hatchling'))"

    Write-Host "==> Running blocking Ruff checks"
    python -m ruff check . --ignore E501,I001

    Write-Host "==> Running advisory Ruff checks"
    python -m ruff check . --select E501,I001

    if ($LASTEXITCODE -ne 0) {
        Write-Warning (
            "Ruff reported advisory E501 or I001 findings."
        )
    }

    Write-Host "==> Checking Ruff formatting"
    python -m ruff format --check .

    Write-Host "==> Running mypy"
    python -m mypy src

    Write-Host "==> Running tests with coverage"
    python -m pytest `
        --cov=automated_screen_recorder `
        --cov-report=term-missing `
        --cov-report=xml:coverage.xml

    if (-not (Test-Path "coverage.xml")) {
        throw "coverage.xml was not generated."
    }

    $Coverage = Get-Item "coverage.xml"

    if ($Coverage.Length -eq 0) {
        throw "coverage.xml is empty."
    }

    Write-Host (
        "Coverage report generated: " +
        "$($Coverage.FullName)"
    )

    Write-Host "==> Removing previous build artifacts"

    if (Test-Path "dist") {
        Remove-Item "dist" -Recurse -Force
    }

    if (Test-Path "build") {
        Remove-Item "build" -Recurse -Force
    }

    Write-Host "==> Building wheel and source distribution"
    python -m build

    $Distributions = @(
        Get-ChildItem -Path "dist" -File |
            Where-Object {
                $_.Extension -eq ".whl" -or
                $_.Name.EndsWith(".tar.gz")
            }
    )

    if ($Distributions.Count -lt 2) {
        throw (
            "Expected a wheel and source distribution, " +
            "but the expected build artifacts were not found."
        )
    }

    Write-Host "==> Validating distributions"

    python -m twine check @(
        $Distributions.FullName
    )

    $Wheels = @(
        Get-ChildItem `
            -Path "dist" `
            -Filter "*.whl" `
            -File
    )

    if ($Wheels.Count -ne 1) {
        throw (
            "Expected exactly one wheel, but found " +
            "$($Wheels.Count)."
        )
    }

    Write-Host (
        "Wheel generated: " +
        "$($Wheels[0].FullName)"
    )

    Write-Host "==> Building standalone executable"

    python -m PyInstaller `
        --clean `
        --noconfirm `
        --onefile `
        --name autoscreenrec `
        scripts/standalone_entry.py

    if (-not (Test-Path "dist/autoscreenrec.exe")) {
        throw (
            "Standalone Windows executable was not generated."
        )
    }

    $Executable = Get-Item "dist/autoscreenrec.exe"

    if ($Executable.Length -eq 0) {
        throw "Standalone Windows executable is empty."
    }

    Write-Host ""
    Write-Host "Build completed successfully."
    Write-Host ""
    Write-Host "Generated artifacts:"

    Get-ChildItem -Path "dist"
}
finally {
    Pop-Location
}
