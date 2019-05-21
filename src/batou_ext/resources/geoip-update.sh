#!/usr/bin/env sh

{% if component.host.platform == "nixos" -%}
source /etc/profile
{% endif -%}

curl -O http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz
gunzip -f GeoLite2-City.mmdb.gz
