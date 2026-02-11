#!/bin/bash
set -euxo pipefail

current_branch=$(git rev-parse --abbrev-ref HEAD)

if [ "$current_branch" != "master" ]; then
    set +x
    echo
    echo
    echo "ERROR: can only release from master. We are on $current_branch"
    echo
    exit 1
fi

changes=$(git status --porcelain)
if [ -n "$changes" ]; then
    set +x
    echo
    echo
    echo "ERROR: there are changes."
    echo
    git status
    exit 1
fi

cd $(dirname $0)

envdir=$(mktemp -d)
uv venv $envdir
uv pip install -p $envdir/bin/python zest.releaser scriv


$envdir/bin/scriv collect

sed  -i .orig '/- Nothing changed yet./ { N; d; } ' CHANGES.md
git add -A .
git status
PAGER= git diff --cached
echo "Press enter to commit, Ctrl-C to abort."
read
git commit -m "Prepare changelog for release"

$envdir/bin/fullrelease

rm -rf $envdir
