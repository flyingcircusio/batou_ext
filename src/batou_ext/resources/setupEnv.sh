#!/usr/bin/env nix-shell
#! nix-shell {{component.workdir}}/{{component.python}}.nix -i bash

starter=$1
shift 1

# Remove nixos distutils config from PYTHONPATH. Virtualenv completely
# freaks out when seeing it.
export PYTHONPATH=$(echo ${PYTHONPATH} | awk -v RS=: -v ORS=: '/{{component.python}}-distutils.cfg/ {next} {print}' | sed 's/:*$//')

# TEMP is set to a ramdisk here (/run/user). There is not enough space there for
# compiling lxml or alike. Just use defaults (/tmp).
unset TEMP
unset TMP
unset TMPDIR

exec -a $starter {{component.python}} "$@"
