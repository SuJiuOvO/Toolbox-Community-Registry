#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
cargo build --target wasm32-wasip1 --release
mkdir -p bin
cp target/wasm32-wasip1/release/image_pixel_richtext.wasm bin/
printf '%s\n' "Built bin/image_pixel_richtext.wasm"
