#!/bin/zsh
# Set up the project's development environment.

set -euo pipefail

cd -- "$(dirname -- "$0")"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    print -u2 "nvm not found. Install nvm before running setup."
    exit 1
fi

source "$NVM_DIR/nvm.sh"
nvm install
nvm use

expected_node_version="$(cat .nvmrc)"
if [[ "$(node --version)" != "v${expected_node_version}" ]]; then
    print -u2 "Node.js $expected_node_version is required."
    exit 1
fi

expected_npm_version="$(node -p 'require("./package.json").engines.npm')"
if [[ "$(npm --version)" != "$expected_npm_version" ]]; then
    print -u2 "npm $expected_npm_version is required."
    exit 1
fi

python_cmd=""
for candidate in python3 ${(k)commands}; do
    if [[ "$candidate" != python3 && "$candidate" != python3.<-> ]]; then
        continue
    fi
    if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))' 2>/dev/null; then
        python_cmd="$candidate"
        break
    fi
done

if [[ -z "$python_cmd" ]]; then
    print -u2 "Python 3.13 or newer is required."
    exit 1
fi

"$python_cmd" -m venv .venv
.venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade pip
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

npm ci

print ""
print "Setup complete."
print ""
