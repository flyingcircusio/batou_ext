import json
import shlex
import subprocess
from os import environ
from sys import exit
from typing import Dict, List, Union

import boto3
from InquirerPy import inquirer


class ANSIColors:
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def error(msg):
    print(ANSIColors.FAIL + str(msg) + ANSIColors.ENDC)


def print_bold(msg):
    print(ANSIColors.BOLD + str(msg) + ANSIColors.ENDC)


def remote_sudo(host: str, password: str, cmd: List[str]) -> str:
    cmd_ = " ".join(shlex.quote(x) for x in cmd)
    print_bold(f"[{host}]$ sudo -S {cmd_}")
    proc = subprocess.Popen(
        ["ssh", host, f"sudo -S {cmd_}"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = map(
        lambda x: x.decode("utf-8"),
        proc.communicate(input=bytes(f"{password}\n", "utf-8")),
    )

    exit_code = proc.wait()
    if exit_code != 0:
        raise Exception(
            f"Remote command {cmd} on {host} failed with exit code {exit_code}\nStdout:\n{out}\n\nStderr:{err}!"
        )

    return out


def rg_account_exists(name: str, host: str, sudo_password: str) -> bool:
    return name in json.loads(
        remote_sudo(host, sudo_password, ["radosgw-admin", "user", "list"])
    )


class Step:
    def __str__(self) -> str:
        return "Unknown step"

    def verify(self, previous_result):
        pass

    def apply(self, previous_result):
        pass


class Plan:
    steps: List[Step] = []

    def __add__(self, step: Step):
        self.steps.append(step)
        return self

    def __str__(self) -> str:
        return "\n".join(f" - {str(s)}" for s in self.steps)

    def apply(self):
        previous_result = None
        for step in self.steps:
            try:
                step.verify(previous_result)
            except StateAlreadyExists as e:
                error(e)
                print_bold("Aborting")
                exit(1)
            except ConfigurationError as e:
                error(e)
                print_bold("Aborting")
                exit(1)
            previous_result = step.apply(previous_result)


class StateAlreadyExists(Exception):
    pass


class ConfigurationError(Exception):
    pass


class CreateS3Account(Step):
    def __init__(self, name: str, sudo_password: str, host: str):
        self.name = name
        self.sudo_password = sudo_password
        self.host = host

    def __str__(self) -> str:
        return f"Create S3 account 'RG {self.name}'"

    def verify(self, _):
        if rg_account_exists(self.name, self.host, self.sudo_password):
            raise StateAlreadyExists(f"S3 account {self.name} already exists!")

    def apply(self, _):
        remote_sudo(
            self.host,
            self.sudo_password,
            [
                "radosgw-admin",
                "user",
                "create",
                "--uid",
                self.name,
                "--display-name",
                f"RG {self.name}",
            ],
        )

        return True


class Keypair:
    def __init__(self, key_id: str, secret_key: str):
        self.key_id = key_id
        self.secret_key = secret_key


class CreateKeypair(Step):
    def __init__(self, rg_name: str, sudo_password: str, host: str):
        self.rg_name = rg_name
        self.sudo_password = sudo_password
        self.host = host

    def __str__(self) -> str:
        return f"Generate keypair for account 'RG {self.rg_name}'"

    def verify(self, account_created):
        if not account_created and not rg_account_exists(
            self.rg_name, self.host, self.sudo_password
        ):
            raise ConfigurationError(
                f"Account for rg {self.rg_name} does not exist!"
            )

    def apply(self, _) -> Keypair:
        data = json.loads(
            remote_sudo(
                self.host,
                self.sudo_password,
                [
                    "radosgw-admin",
                    "key",
                    "create",
                    "--uid",
                    self.rg_name,
                    "--gen-access-key",
                ],
            )
        )
        kp = Keypair(
            data["keys"][-1]["access_key"], data["keys"][-1]["secret_key"]
        )

        print(f"AWS_ACCESS_KEY_ID={kp.key_id}")
        print(f"AWS_SECRET_ACCESS_KEY={kp.secret_key}")

        return kp


class CreateBucket(Step):
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f"Create bucket {self.name}"

    def verify(self, key: Union[Keypair, None]):
        print_bold(f"Creating bucket {self.name}...")
        kwargs = {"endpoint_url": "https://files.flyingcircus.io/"}
        if key is not None:
            kwargs["aws_access_key_id"] = key.key_id
            kwargs["aws_secret_access_key"] = key.secret_key
        self.resource = boto3.resource("s3", **kwargs)
        self.client = boto3.client("s3", **kwargs)

        self.bucket = self.resource.Bucket(self.name)
        if self.bucket.creation_date:
            raise StateAlreadyExists(
                f"Bucket with name {self.name} already exists!"
            )

    def apply(self, keys):
        self.bucket.create()
        return self.client


class Rules:
    rules: Dict[str, int] = {}

    def __iter__(self):
        return iter(self.rules.items())

    def __len__(self):
        return len(self.rules)

    def add(self, prefix: str, days: int):
        if prefix in self.rules:
            raise KeyError(f"Key '{prefix}' already has a rule")
        self.rules[prefix] = days

    def __str__(self) -> str:
        return ", ".join(
            f"'{prefix}' expires in {days} days" for prefix, days in self
        )


class CreateLifecyclePolicyConfiguration(Step):
    def __init__(self, bucket: str, rules: Rules):
        self.bucket = bucket
        self.rules = rules

    def __str__(self) -> str:
        return f"Create {len(self.rules)} lifecycle configuration(s) for s3://{self.bucket} ({self.rules})"

    def apply(self, client):
        print_bold("Creating lifecycle rules...")
        client.put_bucket_lifecycle_configuration(
            Bucket=self.bucket,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "Expiration": {"Days": days},
                        "Prefix": prefix,
                        "Status": "Enabled",
                    }
                    for prefix, days in self.rules
                ]
            },
        )


def ask_sudo_password() -> str:
    return inquirer.secret(
        message="What's your FCIO password (needed to run radosgw-admin)?"
    ).execute()


def run():
    print_bold(
        "Interactively creating an S3 bucket + keys as described in https://wiki.flyingcircus.io/S3"
    )

    plan = Plan()
    sudo_password = None
    ceph_osd_host = None
    rg_name = inquirer.text(message="What's the name of the RG?").execute()
    keypair_needed = False
    if inquirer.confirm(message="Does the RG need to be created?").execute():
        keypair_needed = True
        sudo_password = ask_sudo_password()
        ceph_osd_host = inquirer.text(
            message="Which host to use to call radosgw-admin (must be an FQDN)?"
        ).execute()
        plan += CreateS3Account(rg_name, sudo_password, ceph_osd_host)

    if (
        keypair_needed
        or inquirer.confirm(
            message="Do you need a keypair for access?"
        ).execute()
    ):
        if sudo_password is None:
            sudo_password = ask_sudo_password()
        if ceph_osd_host is None:
            ceph_osd_host = inquirer.text(
                message="Which host to use to call radosgw-admin (must be an FQDN)?"
            ).execute()
        plan += CreateKeypair(rg_name, sudo_password, ceph_osd_host)
    elif not all(
        x in environ for x in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    ):
        error(
            "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY missing from environment"
        )
        exit(1)

    bucket_name = inquirer.text(
        message="What's the name of the bucket?"
    ).execute()
    plan += CreateBucket(bucket_name)

    rules = Rules()
    while inquirer.confirm(
        message="Do you want to create a bucket lifecycle configuration?"
    ).execute():
        try:
            rules.add(
                inquirer.text(
                    message="For which prefix should this policy apply (leading slash will be stripped)?"
                )
                .execute()
                .lstrip("/"),
                int(
                    inquirer.number(
                        message="After how many days should the objects be expired?"
                    ).execute()
                ),
            )
        except KeyError as e:
            print(e)

    if len(rules) > 0:
        plan += CreateLifecyclePolicyConfiguration(bucket_name, rules)

    print_bold("Would perform the following steps:")
    print(plan)

    if inquirer.confirm(message="Does this look OK?").execute():
        plan.apply()
    else:
        print("Abort. Nothing changed.")


def main():
    try:
        run()
    except KeyboardInterrupt:
        print("Interrupt")
        exit(130)
    except EOFError:
        print("Aborted")
        exit(130)


if __name__ == "__main__":
    main()
