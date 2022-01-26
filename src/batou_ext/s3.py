"""S3 operations

Example for downloading a file::


    self += batou_ext.s3.S3(endpoint_url="https://my.s3.endpoint",
                            access_token="1234567890ABCDEF",
                            secret="very_secure!1!")
    self.s3 = self._
    self += batou_ext.s3.Download("my/file/from/bucket",
                                    bucketname="mybucket",
                                    target="download.zip",
                                    s3=self.s3)

To make a bucket available, to e.g. the application::

    self += batou_ext.s3.Bucket('downloads', s3=self.s3)

"""
import os

import batou.component
import batou.utils
import boto3


class S3(batou.component.Component):
    """Configuration for an S3 connection and its credentials."""

    endpoint_url = batou.component.Attribute(str)
    access_key_id = batou.component.Attribute(str)
    secret_access_key = batou.component.Attribute(str)

    def configure(self):
        self.client = boto3.resource(
            "s3",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            endpoint_url=self.endpoint_url)


class Bucket(batou.component.Component):
    """Make given S3 bucket available.

    Usage::

        self += batou_ext.s3.S3Bucket('downloads', s3=self.s3)

    """

    namevar = "bucketname"
    s3 = batou.component.Attribute()

    def configure(self):
        self.bucket = self.s3.client.Bucket(self.bucketname)

    def verify(self):
        if not self.bucket.creation_date:
            raise batou.UpdateNeeded()

    def update(self):
        self.bucket.create()


class Download(batou.component.Component):
    """
    Downloads a file from a given S3 instance.

    Usage::

        self += batou_ext.s3.Download("my/file/from/bucket"
                                        s3,
                                        bucketname="mybucket")
    """

    namevar = 'key'
    s3 = batou.component.Attribute(str)
    key = batou.component.Attribute(str)
    bucketname = batou.component.Attribute(str)
    target = batou.component.Attribute(str)

    # Optional checksum. If given it is used as "must download" indicator,
    # otherwise the the file's ETAG from S3 is used.
    checksum = None

    def configure(self):
        if self.checksum:
            self.checksum_function, self.checksum = self.checksum.split(":")
        else:
            self.etag_file = self.target + ".etag"

        self.obj = self.s3.client.Object(self.bucketname, self.key)
        self.target = self.map(self.target)

    def verify(self):
        if not os.path.exists(self.target):
            raise batou.UpdateNeeded()
        if self.checksum:
            if self.checksum != batou.utils.hash(self.target,
                                                 self.checksum_function):
                raise batou.UpdateNeeded()
        else:
            if not os.path.exists(self.etag_file):
                raise batou.UpdateNeeded()
            with open(self.etag_file) as f:
                current_etag = f.read()
                if current_etag != self.obj.e_tag:
                    raise batou.UpdateNeeded()

    def update(self):
        self.obj.download_file(self.target)
        if self.checksum:
            target_checksum = batou.utils.hash(self.target,
                                               self.checksum_function)
            assert (self.checksum == target_checksum), """\
Checksum mismatch!
expected: %s
got: %s""" % (
                self.checksum,
                target_checksum,
            )
        with open(self.etag_file, "w") as f:
            f.write(self.obj.e_tag)
