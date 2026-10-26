#!/bin/sh
# This Source Code Form is subject to the Mozilla Public License, v. 2.0.
# See the LICENSE file or https://mozilla.org/MPL/2.0/.
set -eu
: "${G1_REAL_CARGO:?Set G1_REAL_CARGO before adding this wrapper to PATH}"

case "${1:-}" in
    build|check|fetch|metadata|tree|test)
        g1_cargo_command=$1
        shift
        g1_has_locked=no
        for g1_arg in "$@"; do
            [ "$g1_arg" != --locked ] || g1_has_locked=yes
        done
        if [ "$g1_has_locked" = no ]; then
            set -- --locked "$@"
        fi
        printf 'G1 locked Cargo invocation: %s\n' "$g1_cargo_command" >&2
        exec "$G1_REAL_CARGO" "$g1_cargo_command" "$@"
        ;;
    *)
        exec "$G1_REAL_CARGO" "$@"
        ;;
esac

