# This file is managed by batou. Don't edit manually.
{ ... }:
{
  environment.etc."modsecurity/{{component.ruleset_name}}_main.conf".text = ''
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
       SecAuditLog /var/log/nginx/modsec_{{component.ruleset_name}}_audit.log
       SecArgumentSeparator &
       SecCookieFormat 0
       SecUnicodeMapFile {{component.unicode_map_file}} 20127
       SecStatusEngine On

       {%- if component.enable_crs %}

       # CRS specific configuration
       include {{component.checkout_target}}/rules/*.conf
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

       {%- endif %}

       # Includes directory for new rules
       include {{component.includes_directory}}/*.conf
    '';
}
