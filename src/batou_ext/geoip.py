import os.path

import batou.component
import batou.lib.file

import batou_ext.cron


class GeoIPDatabase(batou.component.Component):
    """
    A small component to download a GeoIP-database and keep downloaded
    up to date.

    Usage

    self += batou_ext.geoip.GeoIPDatabase()
    self.geoipdb = self._.database_file

    Needs curl and gunzip inside $PATH
    """

    license_key = None
    download_url = batou.component.Attribute(
        str,
        batou.component.ConfigString(
            "https://download.maxmind.com/app/geoip_download?"
            "edition_id=GeoLite2-City&suffix=tar.gz&"
            "license_key={{component.license_key}}"
        ),
    )

    def configure(self):

        self.provide("geoip_database", self)
        self += batou.lib.file.File(
            "geoip-update.sh",
            source=os.path.join(
                os.path.dirname(__file__), "resources/geoip-update.sh"
            ),
            mode=0o744,
        )
        self.script = self._.path

        self += batou_ext.cron.CronJob(
            "GeoIP_update",
            command=self.script,
            timing="@weekly",
            timeout="1h",
            checkWarning=15000,
            checkCritical=30000,
        )

        self.database_file = self.expand(
            "{{component.workdir}}/GeoLite2-City.mmdb"
        )

    def verify(self):
        self.assert_no_changes()

    def update(self):
        self.cmd("{{component.workdir}}/geoip-update.sh", expand=True)
