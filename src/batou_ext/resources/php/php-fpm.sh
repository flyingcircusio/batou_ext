#!/usr/bin/env bash

exec php-fpm \
    -y {{component.php_fpm_ini.path}} \
    -c {{component.php_ini.path}} \
    -g {{component.pid_file}}
