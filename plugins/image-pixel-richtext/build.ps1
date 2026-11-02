$ErrorActionPreference = "Stop"
$pluginDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $pluginDir

cargo build --target wasm32-wasip1 --release
New-Item -ItemType Directory -Path "bin" -Force | Out-Null
Copy-Item "target/wasm32-wasip1/release/image_pixel_richtext.wasm" `
  "bin/image_pixel_richtext.wasm" -Force
Write-Host "Built bin/image_pixel_richtext.wasm"
