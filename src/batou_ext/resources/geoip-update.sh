#!/usr/bin/env sh

set -e

{% if component.host.platform == "nixos" -%}
source /etc/profile
{% endif -%}

cd {{component.workdir}}
curl -s "{{component.download_url}}" | tar -xzv --strip-components 1
