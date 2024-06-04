#!/usr/bin/env sh

set -e
declare -i state_ok=0
declare -i state_warning=1
declare -i state_critical=2

expire_date=$(date --date="$(openssl x509 -in "{{component.certificate_path}}" -noout -enddate | cut -d= -f 2)" --iso-8601)
echo "The certificate is valid until $expire_date"

# Check whether it's critical
if ! openssl x509 -checkend {{component.critical_seconds}} -noout -in "{{component.certificate_path}}" >/dev/null
then
    echo "The certificate will expire in less than {{component.critical_days}} days!"
    exit ${state_critical}
fi

# Check whether it's warning
if ! openssl x509 -checkend {{component.warning_seconds}} -noout -in "{{component.certificate_path}}" >/dev/null
then
    echo "The certificate will expire in less than {{component.warning_days}} days!"
    exit ${state_warning}
fi

# Seems to be ok
exit ${state_ok}
