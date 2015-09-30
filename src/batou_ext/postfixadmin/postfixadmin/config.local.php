<?php
// This file is managed by batou. DO NOT EDIT
//
// If changes are needed, send an email to support@flyingcircus.io,
// so we can update the deployment.

$CONF['configured'] = true;
$CONF['setup_password'] = '{{component.admin_password_encrypted}}';

$CONF['database_type'] = '{{component.db.dbms}}';
$CONF['database_host'] = '{{component.db.address.connect.host}}';
$CONF['database_user'] = '{{component.db.username}}';
$CONF['database_password'] = '{{component.db.password}}';
$CONF['database_name'] = '{{component.db.database}}';

$CONF['smtp_server'] = '{{component.postfix.connect.host}}';
$CONF['smtp_port'] = '{{component.postfix.connect.port}}';

$CONF['encrypt'] = 'dovecot:SHA256-CRYPT';
$CONF['dovecotpw'] = "/usr/bin/doveadm pw";

$CONF['vacation'] = 'NO';

$CONF['sendmail'] = 'NO';
$CONF['fetchmail'] = 'NO';

$CONF['show_footer_text'] = 'NO';
