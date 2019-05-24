#!/bin/sh

{% if component.host.platform == "nixos" -%}
source /etc/profile
{% endif -%}

{% for key, value in component.env.items() | sort -%}
export {{key}}='{{value}}'
{% endfor %}

exec php-fpm \
    -y {{component.php_fpm_ini}} \
    -c {{component.php_ini}} \
    -g {{component.pid_file}}
