$ErrorActionPreference = 'Stop'

$pluginRoot = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $pluginRoot 'bin\windows-fast-file-shuttle.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
  throw "Executable not found: $exe"
}

$tempPrefix = 'multi-toolbox-fast-file-smoke-'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ($tempPrefix + [guid]::NewGuid().ToString('N'))

function Assert-True([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
}

try {
  $source = Join-Path $testRoot 'source'
  $copyTarget = Join-Path $testRoot 'copy-target'
  $moveTarget = Join-Path $testRoot 'move-target'
  $dryRunTarget = Join-Path $testRoot 'dry-run-target'
  New-Item -ItemType Directory -Path $source, $copyTarget, $moveTarget, $dryRunTarget -Force | Out-Null

  foreach ($directoryIndex in 0..7) {
    $directory = Join-Path $source ('folder-' + $directoryIndex)
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    foreach ($fileIndex in 0..19) {
      $relative = Join-Path ('folder-' + $directoryIndex) ('file-' + $fileIndex + '.txt')
      [IO.File]::WriteAllText(
        (Join-Path $source $relative),
        ('payload-' + $directoryIndex + '-' + $fileIndex),
        [Text.UTF8Encoding]::new($false)
      )
    }
  }
  [IO.File]::WriteAllBytes((Join-Path $source 'empty.bin'), [byte[]]@())

  $copyDestination = Join-Path $copyTarget (Split-Path $source -Leaf)
  New-Item -ItemType Directory -Path $copyDestination -Force | Out-Null
  [IO.File]::WriteAllText((Join-Path $copyDestination 'same.txt'), 'old-target')
  [IO.File]::WriteAllText((Join-Path $source 'same.txt'), 'new-source')

  & $exe --source $source --target $copyTarget --mode copy --conflict skip --threads 8 --dry-run false
  Assert-True ($LASTEXITCODE -eq 0) 'Copy failed'
  Assert-True ((Get-Content (Join-Path $copyDestination 'same.txt') -Raw) -eq 'old-target') 'Skip conflict failed'
  Assert-True ((Get-ChildItem $source -Recurse -File).Count -eq (Get-ChildItem $copyDestination -Recurse -File).Count) 'Copied file count mismatch'

  & $exe --source $source --target $copyTarget --mode copy --conflict rename --threads 8 --dry-run false
  Assert-True ($LASTEXITCODE -eq 0) 'Rename conflict copy failed'
  Assert-True (Test-Path (Join-Path $copyDestination 'same (1).txt')) 'Rename conflict output missing'

  & $exe --source $source --target $copyTarget --mode copy --conflict overwrite --threads 8 --dry-run false
  Assert-True ($LASTEXITCODE -eq 0) 'Overwrite conflict copy failed'
  Assert-True ((Get-Content (Join-Path $copyDestination 'same.txt') -Raw) -eq 'new-source') 'Overwrite conflict failed'

  & $exe --source $source --target $dryRunTarget --mode move --conflict skip --threads 4 --dry-run true
  Assert-True ($LASTEXITCODE -eq 0) 'Dry run failed'
  Assert-True (Test-Path (Join-Path $source 'same.txt')) 'Dry run changed the source'
  Assert-True (-not (Test-Path (Join-Path $dryRunTarget (Split-Path $source -Leaf)))) 'Dry run created output'

  $nestedTarget = Join-Path $source 'nested-target'
  New-Item -ItemType Directory -Path $nestedTarget -Force | Out-Null
  $previousErrorAction = $ErrorActionPreference
  $ErrorActionPreference = 'SilentlyContinue'
  & $exe --source $source --target $nestedTarget --mode copy --conflict skip --threads 4 --dry-run false 2>$null | Out-Null
  $overlapExit = $LASTEXITCODE
  $ErrorActionPreference = $previousErrorAction
  Assert-True ($overlapExit -eq 1) 'Overlapping source and target were not rejected'

  $ErrorActionPreference = 'SilentlyContinue'
  & $exe --source ($env:SystemDrive + '\') --target $dryRunTarget --mode copy --conflict skip --threads 4 --dry-run true 2>$null | Out-Null
  $driveRootExit = $LASTEXITCODE
  $ErrorActionPreference = $previousErrorAction
  Assert-True ($driveRootExit -eq 1) 'Drive-root source was not rejected'

  & $exe --source $source --target $moveTarget --mode move --conflict skip --threads 8 --dry-run false
  Assert-True ($LASTEXITCODE -eq 0) 'Move failed'
  $moveDestination = Join-Path $moveTarget (Split-Path $source -Leaf)
  Assert-True ((Get-ChildItem $moveDestination -Recurse -File).Count -eq 162) 'Moved file count mismatch'
  Assert-True (-not (Test-Path (Join-Path $source 'same.txt'))) 'Moved source still exists'

  Write-Host 'Smoke test passed: copy, move, conflicts, dry-run, overlap and drive-root guards.'
}
finally {
  $resolved = [IO.Path]::GetFullPath($testRoot)
  $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  if ($resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
      [IO.Path]::GetFileName($resolved).StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
      [IO.Directory]::Exists($resolved)) {
    [IO.Directory]::Delete($resolved, $true)
  }
}
