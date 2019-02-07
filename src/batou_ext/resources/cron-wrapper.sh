#!/bin/sh
set -e

exec 9>> {{component.lock_file}}
flock -n 9

{{component.command}}

touch {{component.stamp_file}}
