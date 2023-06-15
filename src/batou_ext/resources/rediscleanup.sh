#!/bin/sh

source /etc/profile

redis-cli -a {{component.password}} -n {{component.db}} {{component.cleanup_command}}
