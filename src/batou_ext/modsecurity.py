import batou.component
import batou.lib.file
import batou_ext.nix
import os


@batou_ext.nix.rebuild
class ModSecurity(batou.component.Component):
    '''
    Manages one or more mod_security rule sets for nginx, including the "OWASP Core Rule Set".

    Without any parameters this creates a basic default rules file on the lowest paranoia
    level and logs events but does not block anything.

    Specific rule files need to be enabled through your project's nginx configuration,
    typically by enabling mod_security and choosing the profile:

         server {
             modsecurity on;
             modsecurity_rules_file /etc/modsecurity_includes_default.conf
         }


    ## Default usage:

         self += Modsecurity()

    This uses the default behaviour:

    - Modsecurity does not block any request, it just logs
    - The Paranoia Level is at 1 which is the lowest setting


    ## Customize attributes

    You may change these by giving other attribute values.

          self += Modsecurity(block=True, paranoia_level=20)

    ## Adding new rules

    At this Paranoia Level it may be necessary to change some configuration
    to negate false positives. You may add new configuration files, which will be placed
    at the bottom of the includes file. This is done with `includes`, which expects a list
    of strings with the path to the file, or if just one file is added, only a string.

          self += Modsecurity(
              block=True,
              paranoia_level=20,
              includes=['path/to/file1', 'path/to/file2']
          )

    ## Multiple instances

    It is completly possible to use multiple different rulesets on the same server.
    This is done with the `ruleset_name` attribute. If no value is given it uses `default`.

          self.modsecurity_frontend_1 = Modsecurity(
              ruleset_name='frontend1',
              paranoia_level=20,
              includes='frontend1_exceptions'
          )

          self.modsecurity_frontend_2 = Modsecurity(
              ruleset_name='frontend2',
              block=True,
              includes=['frontend2_exceptions', 'frontend2_additions']
          )

    You can get he includes path for each instance of ModSecurity
    from its `include_path` attribute.
    '''

    block = False
    paranoia_level = 1
    ruleset_name = 'default'
    include_path = f'/etc/modsecurity_includes_{ruleset_name}.conf'
    enable_owasp = True
    # current on branch v3.3/master
    owasp_revision = '18703f1bc47e9c4ec4096853d5fb4e2a204a07a2'
    includes = None

    def configure(self):

        if isinstance(self.includes, str):
            self.includes = [self.includes]
        elif self.includes is None:
            self.includes = list()

        if self.enable_owasp:
            self.checkout_target = self.map(f'owasp-checkouts/{self.ruleset_name}')
            self += batou.lib.file.Directory(self.checkout_target, leading=True)
            self.checkout = batou_ext.git.GitCheckout(
                git_clone_url='https://github.com/coreruleset/coreruleset.git',
                git_revision=self.owasp_revision,
                git_target=self.checkout_target,
               )
            self += self.checkout
            self += self.checkout.symlink_and_cleanup()

        self += batou.lib.file.File(f'/etc/local/nixos/modsecurity-{self.ruleset_name}-configuration.nix',
                                   source=self.resource('modsecurity-configuration.nix'))

    def resource(self, filename):
        return os.path.join(os.path.dirname(__file__), 'resources', filename)
