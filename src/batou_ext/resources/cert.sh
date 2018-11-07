#!/usr/bin/env bash

set -e

{% if component.host.platform == "nixos" -%}
source /etc/profile
{% endif -%}

{{component.workdir}}/dehydrated \
    --config {{component.config.path}} \
    --register --accept-terms

{{component.workdir}}/dehydrated \
    --config {{component.config.path}} \
    --out {{component.workdir}} \
    -c "$@"
{% if component.extracommand %}
{{component.extracommand}}
{% endif %}
