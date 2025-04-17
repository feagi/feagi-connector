# PowerShell script to build and test the Rust library for Python

# Stop on any error
$ErrorActionPreference = "Stop"

Write-Host "Building Rust library for Python..."
Set-Location -Path .\rust_core_sensiomotor_functions_py
cargo build --release

Write-Host "`nChecking for compiled library..."
# Find the compiled library
$libPath = Get-ChildItem -Path .\target\release -Recurse -Include "*.dll","*.pyd" | 
           Where-Object { $_.FullName -notmatch '\.d\.' } |
           Select-Object -First 1 -ExpandProperty FullName

if (-not $libPath) {
    Write-Host "Error: Could not find compiled library" -ForegroundColor Red
    exit 1
}

Write-Host "Found library at: $libPath"

# Extract just the filename
$libFilename = Split-Path -Path $libPath -Leaf

# Verify the module name
Write-Host "`nVerifying module name..."
if (-not $libFilename.StartsWith("FEAGI_Connector")) {
    Write-Host "Warning: Library filename ($libFilename) does not match expected module name (FEAGI_Connector)" -ForegroundColor Yellow
    Write-Host "This might prevent Python from importing it correctly"
    
    # See what the actual module name might be
    $potentialModuleName = $libFilename.Split('.')[0]
    Write-Host "Python might try to import it as '$potentialModuleName' instead of 'FEAGI_Connector'"
}

Set-Location -Path ..
Write-Host "`nRunning test script..."
python test_import.py 