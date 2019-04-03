#!/bin/sh

exec php-fpm \
    -y {{component.php_fpm_ini}} \
    -c {{component.php_ini}} \
    -g {{component.pid_file}}
