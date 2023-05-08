from textwrap import dedent
import batou.component
import batou.lib.file
import batou_ext.nix
import os


@batou_ext.nix.rebuild
class ModSecurity(batou.component.Component):
    '''
    Manages one or more ModSecurity rule sets for nginx, including the OWASP
    Core Rule Set (CRS).

    Without any parameters this creates a basic default rules file on the lowest
    paranoia level and logs events but does not block anything.

    Specific rule files need to be enabled through your project's Nginx configuration,
    typically by enabling ModSecurity and choosing the profile:

         server {
             modsecurity on;
             modsecurity_rules_file /etc/modsecurity/default_main.conf
         }


    ## Default usage

         self += ModSecurity()

    This has the default behaviour:

    - ModSecurity does not block any request, it just logs
    - The configuration file that has to be reverenced in the Nginx configuration
      is writen to `/etc/modsecurity/default_main.conf`
    - CRS is used
    - Its Paranoia Level is set to 1


    ## Customize attributes

    You may change these by giving other attribute values.

          self += ModSecurity(block=True, paranoia_level=20)


    ## Adding new rules

    At this Paranoia Level it may be necessary to change the configuration
    to negate false positives. You may add new configuration files, which will be
    loaded after everything else. This is done by placing the files into the
    includes directory. By default this is `/etc/local/nginx/modsecurity/default_includes/`.


    ## Multiple instances

    It is possible to use multiple different rulesets on the same server.
    This is done with the `ruleset_name` attribute. If no value is given it uses `default`.

          self.frontend1 = ModSecurity(
              ruleset_name='frontend1',
              paranoia_level=20,
          )
          self += self.frontend1

          self.frontend2 = ModSecurity(
              ruleset_name='frontend2',
              block=True,
          )
          self += self.frontend2


    ## Endpoints

          self.example = ModSecurity()
          self += self.example

    ### main_path

    Location of configuration file that has to be referenced by Nginx

          x = self.example.main_path

    ### includes_directory

    Location of the directory in which all *.conf files are included

          x = self.example.includes_directory
    '''

    block = False
    paranoia_level = 1
    ruleset_name = 'default'

    main_path = f'/etc/modsecurity/{ruleset_name}_main.conf'
    # These are the locations, if the Flying Circus Webgateway role is used.
    # If ModSecurity is installed otherwise the locations may differ.
    includes_directory = f'/etc/local/nginx/modsecurity/{ruleset_name}_includes'
    unicode_map_file = '/etc/local/nginx/modsecurity/unicode.mapping'

    enable_crs = True
    # current on branch v3.3/master
    crs_revision = '18703f1bc47e9c4ec4096853d5fb4e2a204a07a2'

    def configure(self):

        if self.enable_crs:
            self.checkout_target = self.map(f'crs-checkouts/{self.ruleset_name}')
            self += batou.lib.file.Directory(self.checkout_target, leading=True)
            self.checkout = batou_ext.git.GitCheckout(
                git_clone_url='https://github.com/coreruleset/coreruleset.git',
                git_revision=self.crs_revision,
                git_target=self.checkout_target,
               )
            self += self.checkout
            self += self.checkout.symlink_and_cleanup()

        self += batou.lib.file.Directory(self.includes_directory, leading=True)
        self += batou.lib.file.File(f'{self.includes_directory}/crs-version.conf',
                                    content = '''
            # This file is managed by batou. Don't edit manually.

            # This action is used by CRS to check if config is loaded succesfully
            SecAction
             "id:900990,\
              phase:1,\
              nolog,\
              pass,\
              t:none,\
              setvar:tx.crs_setup_version=320"
                                    ''')
        self += batou.lib.file.File(f'/etc/local/nixos/modsecurity-{self.ruleset_name}.nix',
                                   source=self.resource('modsecurity.nix'))

    def resource(self, filename):
        return os.path.join(os.path.dirname(__file__), 'resources', filename)
