from batou.component import Component, Attribute
from batou.lib.file import File
from batou.lib.supervisor import Program
from batou.lib.nagios import ServiceCheck
from batou.utils import Address
import os


class FPM(Component):

    namevar = 'proc'

    address = Address('127.0.0.1', 9001)
    php_fpm = '/usr/bin/php-fpm'
    php_fpm_conf = os.path.join(
        os.path.dirname(__file__), 'resources', 'php-fpm.conf')

    def configure(self):

        fpm_config = File('php-fpm.conf', source=self.php_fpm_conf)
        self += fpm_config

        self += Program(
            self.proc,
            command='{} -y {}'.format(self.php_fpm, fpm_config.path))

        self += ServiceCheck(
            '{} FCGI port'.format(self.proc),
            nrpe=True,
            name='{}_FCGI_port'.format(self.proc),
            command=self.expand(
                '/usr/lib/nagios/plugins/check_tcp '
                '-p {{component.address.connect.port}} '
                '-H {{component.address.connect.host}} '
                '-w 3 -c 10 -t 60'))
