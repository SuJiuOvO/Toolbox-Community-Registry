$ErrorActionPreference = 'Stop'

$pluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $pluginRoot 'src\fast_file_shuttle.cpp'
$manifest = Join-Path $pluginRoot 'src\long_path.manifest'
$resourceScript = Join-Path $pluginRoot 'src\resource.rc'
$resourceObject = Join-Path $pluginRoot 'src\resource.o'
$outputDir = Join-Path $pluginRoot 'bin'
$output = Join-Path $outputDir 'windows-fast-file-shuttle.exe'

$gpp = (Get-Command 'g++.exe' -ErrorAction Stop).Source
$windres = (Get-Command 'windres.exe' -ErrorAction Stop).Source

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
& $windres --include-dir (Join-Path $pluginRoot 'src') $resourceScript -O coff -o $resourceObject
if ($LASTEXITCODE -ne 0) {
  throw "windres failed with exit code $LASTEXITCODE"
}

& $gpp `
  -std=c++17 `
  -O2 `
  -DNDEBUG `
  -DUNICODE `
  -D_UNICODE `
  -DWIN32_LEAN_AND_MEAN `
  -municode `
  -s `
  -Wall `
  -Wextra `
  $source `
  $resourceObject `
  -o $output `
  -static `
  -static-libgcc `
  -static-libstdc++ `
  '-Wl,--dynamicbase,--nxcompat,--high-entropy-va' `
  -lkernel32
if ($LASTEXITCODE -ne 0) {
  throw "g++ failed with exit code $LASTEXITCODE"
}

Remove-Item -Force $resourceObject
Write-Host "Built: $output"
