#!/usr/bin/env bash

{{component.workdir}}/dehydrated \
    --config {{component.config.path}} \
    --out {{component.workdir}} \
    -c
{% if component.extracommand %}
{{component.extracommand}}
{% endif %}
