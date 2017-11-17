import batou_ext.nix
import batou.component
import batou.lib.file
import hashlib
import os.path


class PHPEnvironment(batou.component.Component):

    name = None
    namevar = 'name'

    # Generic php.ini overwrites as a string
    # Will be added to generated php.ini
    # Consider not mixing with php_ini argument
    ini_overrides = batou.component.Attribute(str, '')

    # Version of PHP to be installed idendified by Nix-attribute
    php_attribute = batou.component.Attribute(str, 'nixos.php70')

    # Provide your own php.ini
    php_ini = None

    # Providoe your own php-fpm.conf
    php_fpm_ini = None
    php_fpm_ini_global_overrides = batou.component.Attribute(str, '')
    php_fpm_ini_pool_overrides = batou.component.Attribute(str, '')

    opcache_dir = batou.component.Attribute(str, 'no-debug-zts-20151012')
    extensions = ()
    additional_checksum = ()
    fcgi_timeout = "30s"

    fpm_port = batou.component.Attribute(int, 9001)

    def configure(self):
        checksum = hashlib.new('md5')
        for s in self.additional_checksum:
            checksum.update(s)

        # External address.
        self.fpm_address = batou.utils.Address(self.host.fqdn, self.fpm_port)

        self._extensions_dir = os.path.expanduser(
            '~/.nix-profile/lib/php/extensions/')

        # Enable threads in PHP, required for redis.
        self += batou.lib.file.File('~/.nixpkgs', ensure='directory')
        self += batou.lib.file.File('~/.nixpkgs/config.nix',
                                    content="""\
{
  php.zts = true;
}
""")

        self += batou_ext.nix.Package(attribute=self.php_attribute)
        checksum.update(self.php_attribute)

        # Folder for logfiles
        self += batou.lib.file.File('logs', leading=True, ensure='directory')
        self.logfiledir = self._
        self += batou.lib.logrotate.RotatedLogfile(
            self.expand('{{component.logfiledir.path}}/*.log'))

        # Providing a php.ini
        if not self.php_ini:
            self += batou.lib.file.File(
                'php.ini',
                source=os.path.join(
                    os.path.dirname(__file__),
                    'resources/php/php.ini'))
            self.php_ini = self._
        checksum.update(self.php_ini.content)

        # Providing a php-fpm.conf
        if not self.php_fpm_ini:
            self += batou.lib.file.File(
                'php-fpm.conf',
                source=os.path.join(
                    os.path.dirname(__file__),
                    'resources/php/php-fpm.conf'))
            self.php_fpm_ini = self._
        checksum.update(self.php_fpm_ini.content)

        self.pid_file = self.map('php-fpm.pid')
        self += batou.lib.file.File(
            self.name, mode=0o755,
            source=os.path.join(
                os.path.dirname(__file__),
                'resources/php/php-fpm.sh'))
        checksum.update(self._.content)

        self += batou.lib.service.Service(
            self.name,
            checksum=checksum.hexdigest(),
            systemd=dict(
                PIDFile=self.pid_file,
                Restart='always'))
