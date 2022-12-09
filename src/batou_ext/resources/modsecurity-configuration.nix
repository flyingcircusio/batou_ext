{ ... }:
{
  environment.etc."modsecurity_{{component.ruleset_name}}.conf".text = ''
       # This file is managed by batou. Don't edit manually.

       {%- if component.block %}
       # This setting will BLOCK the triggering requests and also LOG them
       SecRuleEngine On
       {%- else %}
       # This setting will NOT block the triggering requests but LOG them
       SecRuleEngine DetectionOnly
       {%- endif %}

       SecRequestBodyAccess On
       SecTmpDir /tmp/
       SecDataDir /tmp/
       SecDebugLog /tmp/debug.log
       SecDebugLogLevel 3
       SecAuditEngine RelevantOnly
       SecAuditLogRelevantStatus "^(?:5|4(?!04))"
       SecAuditLogParts ABIJDEFHZ
       SecAuditLogType Serial
       SecAuditLog /var/log/nginx/modsec_audit.log
       SecArgumentSeparator &
       SecCookieFormat 0
       SecUnicodeMapFile /etc/local/nginx/modsecurity/unicode.mapping 20127
       SecStatusEngine On
    '';

{%- if component.enable_owasp %}
    environment.etc."crs-setup_{{component.ruleset_name}}.conf".text = ''
       # File managed by batou. Don't edit manually

       {%- if component.block %}
       SecDefaultAction "phase:1,log,auditlog,deny,status:401"
       SecDefaultAction "phase:2,log,auditlog,deny,status:401"
       {%- else %}
       SecDefaultAction "phase:1,log,auditlog,pass"
       SecDefaultAction "phase:2,log,auditlog,pass"
       {%- endif %}

       SecCollectionTimeout 600

       SecAction
        "id:100,\
         phase:1,\
         nolog,\
         pass,\
         t:none,\
         setvar:tx.paranoia_level={{component.paranoia_level}}"
       SecAction
        "id:900990,\
         phase:1,\
         nolog,\
         pass,\
         t:none,\
         setvar:tx.crs_setup_version=320"
    '';
{%- endif %}

    environment.etc."modsecurity_includes_{{component.ruleset_name}}.conf".text = ''
        # This file is managed by batou. Don't edit manually.

        include /etc/modsecurity_{{component.ruleset_name}}.conf
        {%- if component.enable_owasp %}
        include /etc/crs-setup_{{component.ruleset_name}}.conf
        include {{component.checkout_target}}/rules/*.conf
        {%- endif %}
        {% for i in component.includes %}
        include {{ i }}
        {% endfor %}
    '';
}
