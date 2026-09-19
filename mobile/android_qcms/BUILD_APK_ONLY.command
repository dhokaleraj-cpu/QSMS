#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export QCMS_BUILD_ONLY=1
exec /bin/bash "$HERE/BUILD_AND_INSTALL_SAMSUNG.command"
