#!/usr/bin/env sh

set -e
declare -i state_ok=0
declare -i state_warning=1
declare -i state_critical=2

# Check whether it's critical
if ! openssl x509 -checkend {{component.critical}} -noout -in "{{component.certificate_path}}"
then
    openssl x509 -in "{{component.certificate_path}}" -noout -enddate
    exit ${state_critical}
fi

# Check whether it's warning
if ! openssl x509 -checkend {{component.warning}} -noout -in "{{component.certificate_path}}"
then
    openssl x509 -in "{{component.certificate_path}}" -noout -enddate
    exit ${state_warning}
fi

# Seems to be ok
exit ${state_ok}
