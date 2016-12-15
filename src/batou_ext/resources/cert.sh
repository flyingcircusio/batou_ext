#!/usr/bin/env bash

{{component.workdir}}/dehydrated \
    --config {{component.config.path}} \
    -d {{component.domain}} \
    --out {{component.workdir}} \
    -c

