import batou.component
import batou.utils
import boto3
import botocore
import os


class S3(batou.component.Component):
    """
        Glueing component for your S3 to keep track of your credentials
        and provide some common actions.

        Usage:

        self += batou_ext.s3.S3(
            endpoint_url="https://my.s3.endpoint",
            access_token="1234567890ABCDEF",
            secret="very_secure!1!",
            provide_name="s3_aws")

        This would you to define different S3 instances for your
        project:

        self.aws = batou_ext.s3.S3(
            [...]
            provide_name="s3_aws")
        [...]
        self.aws += self.require_one("s3_aws"
        self.fcio = batou_ext.s3.S3(
            [...]
            provide_name="s3_fcio")
        self.fcio += self.require_one("s3_fcio"
    """

    endpoint_url = None
    access_key_id = None
    secret_access_key = None

    provide_name = batou.component.Attribute(str, "s3")

    def configure(self):

        if not self.endpoint_url:
            raise ValueError('"endpoint_url" must not be empty.')

        if not self.access_key_id:
            raise ValueError('"access_key_id" must not be empty.')

        if not self.secret_access_key:
            raise ValueError('"secret_access_key" must not be empty.')

        self.provide(self.provide_name, self)

    def _connect(self):
        """
        Returns a s3 resource
        """
        client = boto3.resource(
            "s3",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            endpoint_url=self.endpoint_url,
            config=botocore.client.Config(signature_version="s3"),
        )

        return client

    def _create_bucket(self, bucketname=None):

        if not bucketname:
            raise ValueError('"bucketname" must not be empty.')

        client = self._connect()
        if bucketname not in [i._name for i in self._get_available_buckets()]:
            bucket = client.Bucket(bucketname).create()

    def _get_available_buckets(self):
        """
        Returns a list of bucket-resources
        """
        client = self._connect()
        return client.buckets.all()


class S3Bucket(batou.component.Component):
    """
    This components ensures a bucket is created on your S3 setup.

    Usage:
    self += batou_ext.s3.S3Bucket('downloads')

    In case of not default S3 name or using multiple S3-instances:

    self.fcio = batou_ext.s3.S3(
        [...]
        provide_name="s3_fcio")
    self += self.fcio
    self += batou_ext.s3.S3Bucket(
        'downloads',
        s3=self.fcio)
    """

    namevar = "bucketname"
    s3 = None

    def configure(self):
        if not self.s3:
            self.s3 = self.require_one("s3")

    def verify(self):
        if self.bucketname not in [
            i._name for i in self.s3._get_available_buckets()
        ]:
            raise batou.UpdateNeeded

    def update(self):
        self.s3._create_bucket(self.bucketname)


class S3Download(batou.component.Component):
    """
    Downloads a file from a given S3 instance.

    Usage:
    self += batou_ext.s3.S3Download(
        my_s3,
        bucketname="mybucket",
        key="my/file/from/bucket")
    """

    s3 = None
    key = None
    bucketname = None
    target = None
    checksum = None

    def configure(self):
        if not self.s3:
            self.s3 = self.require_one("s3")

        if not self.key:
            raise ValueError('"key" must not be empty.')
        if not self.bucketname:
            raise ValueError('"bucketname" must not be empty.')
        if not self.target:
            raise KeyError("No target is given.")
        if not self.checksum:
            raise ValueError("No checksum given.")

        self.checksum_function, self.checksum = self.checksum.split(":")

    def verify(self):
        if not os.path.exists(self.target):
            raise batou.UpdateNeeded()
        if self.checksum != batou.utils.hash(
            self.target, self.checksum_function
        ):
            raise batou.UpdateNeeded()

    def update(self):

        s3 = boto3.resource(
            "s3",
            aws_access_key_id=self.s3.access_key_id,
            aws_secret_access_key=self.s3.secret_access_key,
            endpoint_url=self.s3.endpoint_url,
            config=botocore.client.Config(signature_version="s3"),
        )
        s3.Bucket(self.bucketname).download_file(
            self.key, self.map(self.target)
        )

    @property
    def namevar_for_breadcrumb(self):
        return self.key
