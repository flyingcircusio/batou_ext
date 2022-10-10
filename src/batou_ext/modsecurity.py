from textwrap import dedent
import batou.component
import batou.lib.file
import batou_ext.nix


@batou_ext.nix.rebuild
class Modsecurity(batou.component.Component):
    '''
    Performing initial setup of modsecurity for nginx with the OWASP Core Rule Set
    configuration framework. Gives an interface of blocking and Paranoia Level.

    Usage:
    The component is depending on nginx and expects /etc/local/nginx/modsecurity
    to exist.

    Add the Modsecurity-component to your component without customisation.

    self += Modsecurity()

    This uses the default behaviour. They are as follows:
    - Modsecurity does not block any request, it just logs
    - The Paranoia Level is at 10 which is the lowest setting

    You may change these by giving other attribute values.

    self += Modsecurity(block=True, paranoia_level=20)

    At this Paranoia Level it may be necessary to change some configuration
    to negate false positives. You may set new rules with modsec_config for new
    modsecurity rules and owasp_config for new OWAPS Core Rule Set respectifly.

    self += Modsecurity(
        block=True,
        paranoia_level=20,
        owasp_config="SecCollectionTimeout 600",
        modsec_config="SecAuditLog /new/location/modsec_audit.log"
    )

    This can be used to change values that are already set with an different value
    by batou_ext, because the new rules will be placed below the old defaults and
    therefore overwriting them.
    '''

    block = False
    paranoia_level = 10
    component_name = 'default'
    include_path = f'/etc/local/nginx/modsecurity/modsecurity_include_{component_name}.conf'
    # current on branch v3.3/master
    owasp_revision = '18703f1bc47e9c4ec4096853d5fb4e2a204a07a2'
    modsec_config = ''
    owasp_config = ''

    def configure(self):

        self.checkout_target = self.map(f"owasp-checkouts/{self.component_name}")
        self += batou.lib.file.Directory(self.checkout_target, leading=True)
        self.checkout = batou_ext.git.GitCheckout(
            git_clone_url="https://github.com/coreruleset/coreruleset.git",
            git_revision=self.owasp_revision,
            git_target=self.checkout_target,
        )
        self += self.checkout
        self += self.checkout.symlink_and_cleanup()

        self += batou.lib.file.File(self.include_path, content=dedent('''
     # This file is managed by batou. Don't edit manually.

     include /etc/local/nginx/modsecurity/modsecurity_{{component.component_name}}.conf

     include /etc/local/nginx/modsecurity/crs-setup_{{component.component_name}}.conf
     include {{component.checkout_target}}/rules/*.conf
        '''))

        if 'SecRuleEngine' not in self.modsec_config:
            self += batou.lib.file.File(f"/etc/local/nginx/modsecurity/modsecurity_{self.component_name}.conf",
                                        content=dedent('''
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
         SecUnicodeMapFile unicode.mapping 20127
         SecStatusEngine On

         {{component.modsec_config}}
                                        '''))
        else:
            raise Exception('Please use the block attribute to set the blocking behaviour.')

        if 'tx.paranoia_level' not in self.owasp_config:
            self += batou.lib.file.File(f"/etc/local/nginx/modsecurity/crs-setup_{self.component_name}.conf",
                                        content=dedent('''
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
          "id:900990,\
           phase:1,\
           nolog,\
           pass,\
           t:none,\
           setvar:tx.crs_setup_version=320"

         SecAction
          "id:100,\
           phase:1,\
           nolog,\
           pass,\
           t:none,\
           setvar:tx.paranoia_level={{component.paranoia_level}}"

         {{component.owasp_config}}
                                        '''))
        else:
            raise Exception('Please use the paranoia_level attribute to set the Partanoia Level.')
