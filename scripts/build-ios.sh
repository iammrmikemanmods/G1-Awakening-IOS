#!/usr/bin/env bash
# This Source Code Form is subject to the Mozilla Public License, v. 2.0.
# See the LICENSE file or https://mozilla.org/MPL/2.0/.
set -euo pipefail

G1_KIT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
G1_OUTPUT_ROOT=${G1_BUILD_OUTPUT:-"$G1_KIT_ROOT/artifacts"}
G1_WORK_ROOT=${G1_BUILD_WORK:-"${RUNNER_TEMP:-${TMPDIR:-/tmp}}/g1-ios-build-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"}
G1_SOURCE="$G1_WORK_ROOT/Applesauce"
G1_STAGE=initialization
export G1_OUTPUT_ROOT G1_STAGE
mkdir -p "$G1_OUTPUT_ROOT/logs" "$G1_OUTPUT_ROOT/metadata"
exec > >(tee -a "$G1_OUTPUT_ROOT/logs/driver.log") 2>&1

finish() {
    G1_BUILD_EXIT_CODE=$?
    export G1_BUILD_EXIT_CODE G1_STAGE
    python3 - <<'PY'
import datetime, json, os
from pathlib import Path
root = Path(os.environ['G1_OUTPUT_ROOT'])
record = {'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'exit_code': int(os.environ['G1_BUILD_EXIT_CODE']),
          'last_stage': os.environ['G1_STAGE'],
          'ipa_validation_completed': (root/'metadata/ipa-validation.json').exists(),
          'ci': {name: os.environ.get(name) for name in
                 ('GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT',
                  'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_EVENT_NAME')},
          'device_execution_verified': False, 'xr_60fps_verified': False,
          'full_playthrough_verified': False}
(root/'metadata/build-status.json').write_text(json.dumps(record, indent=2)+'\n')
PY
    exit "$G1_BUILD_EXIT_CODE"
}
trap finish EXIT

run_stage() {
    G1_STAGE=$1
    export G1_STAGE
    shift
    printf '\nStage: %s\n' "$G1_STAGE"
    printf 'Command:'
    printf ' %q' "$@"
    printf '\n'
    "$@" 2>&1 | tee "$G1_OUTPUT_ROOT/logs/$G1_STAGE.log"
}

if [ "$(uname -s)" != Darwin ]; then
    echo "An Apple SDK build requires the macOS runner. Use prepare.py for source-only local validation." >&2
    exit 2
fi
for g1_command in git python3 brew rustup; do
    command -v "$g1_command" >/dev/null || { echo "Missing $g1_command" >&2; exit 1; }
done
if [ -e "$G1_WORK_ROOT" ]; then
    echo "Build work directory exists; choose a fresh G1_BUILD_WORK path: $G1_WORK_ROOT" >&2
    exit 1
fi
mkdir -p "$G1_WORK_ROOT/bin"

g1_manifest_value() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]][sys.argv[3]])' \
        "$G1_KIT_ROOT/build-manifest.json" "$1" "$2"
}
DEVELOPER_DIR=$(g1_manifest_value toolchain developer_dir)
G1_XCODE_VERSION=$(g1_manifest_value toolchain xcode_version)
G1_RUST_TOOLCHAIN=$(g1_manifest_value toolchain rust)
G1_RUST_TARGET=$(g1_manifest_value toolchain rust_target)
G1_IPA_NAME=$(g1_manifest_value artifact filename)
export DEVELOPER_DIR
if [ ! -d "$DEVELOPER_DIR" ]; then
    echo "Pinned Xcode is unavailable: $DEVELOPER_DIR. Review the runner image; do not silently change SDKs." >&2
    exit 1
fi
run_stage xcode-version xcodebuild -version
if [ "$(xcodebuild -version | awk '/^Xcode / { print $2; exit }')" != "$G1_XCODE_VERSION" ]; then
    echo "Selected Xcode version differs from the manifest." >&2
    exit 1
fi

run_stage verify-payload python3 "$G1_KIT_ROOT/scripts/prepare.py" --verify-kit \
    --report "$G1_OUTPUT_ROOT/metadata/payload-check.json"
for g1_formula in cmake ninja ldid; do
    if ! command -v "$g1_formula" >/dev/null 2>&1; then
        run_stage "install-$g1_formula" brew install "$g1_formula"
    fi
done
run_stage rust-toolchain rustup toolchain install "$G1_RUST_TOOLCHAIN" --profile minimal --no-self-update
run_stage rust-ios-target rustup target add --toolchain "$G1_RUST_TOOLCHAIN" "$G1_RUST_TARGET"
RUSTUP_TOOLCHAIN=$G1_RUST_TOOLCHAIN
export RUSTUP_TOOLCHAIN
G1_REAL_CARGO=$(rustup which --toolchain "$G1_RUST_TOOLCHAIN" cargo)
RUSTC=$(rustup which --toolchain "$G1_RUST_TOOLCHAIN" rustc)
export G1_REAL_CARGO RUSTC
cp "$G1_KIT_ROOT/scripts/cargo-locked.sh" "$G1_WORK_ROOT/bin/cargo"
chmod +x "$G1_WORK_ROOT/bin/cargo"
PATH="$G1_WORK_ROOT/bin:$PATH"
export PATH

# Keep memory use bounded on the standard runner; these do not alter the guest clock.
CARGO_BUILD_JOBS=2
CMAKE_BUILD_PARALLEL_LEVEL=2
CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true
CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS=false
TOUCHHLE_CPU_BACKEND=interpreter
TOUCHHLE_GUEST_MEMORY=compact
TOUCHHLE_CORE_REPO=
export CARGO_BUILD_JOBS CMAKE_BUILD_PARALLEL_LEVEL
export CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS
export TOUCHHLE_CPU_BACKEND TOUCHHLE_GUEST_MEMORY TOUCHHLE_CORE_REPO

{
    uname -a
    xcodebuild -version
    xcrun --sdk iphoneos --show-sdk-version
    "$RUSTC" --version --verbose
    cargo --version
    cmake --version
    ninja --version
    python3 --version
    brew list --versions ldid || true
    printf 'Runner image: %s / %s\n' "${ImageOS:-not-set}" "${ImageVersion:-not-set}"
    df -h "$G1_WORK_ROOT"
} > "$G1_OUTPUT_ROOT/metadata/tool-versions.txt" 2>&1

run_stage prepare-source python3 "$G1_KIT_ROOT/scripts/prepare.py" --destination "$G1_SOURCE" \
    --report "$G1_OUTPUT_ROOT/metadata/preparation.json"
cd "$G1_SOURCE"
run_stage fetch-locked-dependencies cargo fetch --locked --manifest-path platform/ios/rust-entry/Cargo.toml
CARGO_NET_OFFLINE=true
export CARGO_NET_OFFLINE
G1_STAGE=cargo-feature-resolution
export G1_STAGE
cargo metadata --locked --offline --manifest-path platform/ios/rust-entry/Cargo.toml \
    --filter-platform "$G1_RUST_TARGET" --no-default-features \
    --features cpu-interpreter,compact-memory --format-version 1 \
    > "$G1_OUTPUT_ROOT/metadata/cargo-metadata.json"
run_stage verify-selected-features python3 "$G1_KIT_ROOT/scripts/verify-build.py" \
    --features "$G1_OUTPUT_ROOT/metadata/cargo-metadata.json" \
    --report "$G1_OUTPUT_ROOT/metadata/feature-selection.json"

# Keep the frozen source scripts and their argument handling intact.
run_stage build-shared-sdl sh platform/ios/scripts/build-sdl-shared.sh iphoneos
run_stage build-device-host sh platform/ios/scripts/build-host.sh iphoneos Release
run_stage verify-source-after-build python3 "$G1_KIT_ROOT/scripts/prepare.py" \
    --verify-existing "$G1_SOURCE" --require-submodules \
    --report "$G1_OUTPUT_ROOT/metadata/source-after-build.json"
run_stage package-unsigned-ipa sh platform/ios/scripts/package-ipa.sh "$G1_OUTPUT_ROOT/$G1_IPA_NAME"
run_stage upstream-ipa-verification sh platform/ios/scripts/verify-ipa.sh "$G1_OUTPUT_ROOT/$G1_IPA_NAME"
run_stage verify-arm64-core python3 "$G1_KIT_ROOT/scripts/verify-build.py" \
    --features "$G1_OUTPUT_ROOT/metadata/cargo-metadata.json" \
    --ipa "$G1_OUTPUT_ROOT/$G1_IPA_NAME" --report "$G1_OUTPUT_ROOT/metadata/ipa-validation.json"
cp "$G1_KIT_ROOT/build-manifest.json" "$G1_OUTPUT_ROOT/metadata/build-manifest.json"
cp "$G1_SOURCE/Cargo.lock" "$G1_OUTPUT_ROOT/metadata/Cargo.lock"
git diff --cached --stat > "$G1_OUTPUT_ROOT/metadata/applied-source-diffstat.txt"
G1_STAGE=complete
export G1_STAGE
printf '\nVerified unsigned test host: %s\n' "$G1_OUTPUT_ROOT/$G1_IPA_NAME"
printf 'This build result does not establish iPhone XR execution, sustained 60 FPS, or a full playthrough.\n'
