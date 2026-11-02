#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
cargo build --target wasm32-wasip1 --release
mkdir -p bin
cp target/wasm32-wasip1/release/richtext_pixel_viewer.wasm bin/
printf '%s\n' "Built bin/richtext_pixel_viewer.wasm"
