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
{%- if component.letsencrypt_alternative_chain %}
    --preferred-chain "{{component.letsencrypt_alternative_chain}}" \
{%- endif %}
    -c "$@"

setfacl -Rm u:{{component.granted_user}}:rX {{component.workdir}}/{{component.domain}}

{% if component.extracommand %}
{{component.extracommand}}
{% endif %}
