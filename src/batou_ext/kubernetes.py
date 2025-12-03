import base64
import json
from itertools import groupby
from pathlib import Path

import batou
from batou.component import Attribute, Component
from batou.lib.file import Directory, File, Purge, YAMLContent
from batou.utils import Address
from kubernetes import client, config, utils

import batou_ext.nix


def b64(input: str) -> str:
    return base64.b64encode(input.encode("ascii")).decode("ascii")


class Frontend(Component):
    """
    Frontend address for the services running on the cluster
    """

    ip = Attribute(str)

    _required_params_ = {
        "ip": "127.0.0.1",
    }

    def configure(self):
        self.provide("k3s-address", Address(self.ip, port=0))


class Kubernetes(Component):
    """
    The core part of the kubernetes setup which collects all of the related components.
    It then combines the generated YAML data into one folder and provisions the generated resources.

    This component is not being used directly. Instead simply add this component to a host in your environment.cfg.

    There are two types of components which can be used in this kind of setup: providers and purgers.
    Providers provide resources like secrets, configmaps, PVs, PVCs deployments and services.
    They generate the respective resource's configuration and provide it to this component.

    Purgers on the other hand take care of deprovisioning when resources are not required any more.
    This is necessary due to the underlying imperative approach to managing the kubernetes cluster.
    """

    namespace = Attribute(str, "default")
    yaml_folder = Attribute(Path, Path("~/k3s/"))

    provider_key = Attribute(str, "k3s-provider")
    purger_key = Attribute(str, "k3s-purger")

    def configure(self):
        # you will need to restart the deployment after this fix is first applied
        # since it changes group permissions of the service user
        # self += batou.lib.file.File("/etc/local/nixos/k3sfix.nix")
        self += batou_ext.nix.Rebuild()

        self += Directory(str(self.yaml_folder.expanduser()))

        self._providers = sorted(
            self.require(self.provider_key, strict=False),
            key=lambda p: p._priority,
        )
        self._purgers = sorted(
            self.require(self.purger_key, strict=False),
            key=lambda p: p._priority,
        )

        self._yamls = []

        for _, providers in groupby(self._providers, lambda p: p._priority):
            for provider in providers:
                self += provider
                self += File(
                    self.yaml_folder.joinpath(Path(provider.path).name),
                    source=provider.path,
                )
                self._yamls.append(self._.path)

        for purger in self._purgers:
            self += purger

    def verify(self):
        self.assert_no_changes()
        self.assert_no_subcomponent_changes()

    def update(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()
        apps_api = client.AppsV1Api(k8s_client)
        core_api = client.CoreV1Api(k8s_client)

        for _, purgers in groupby(self._purgers, lambda p: p._priority):
            for purger in purgers:
                purger.purge(
                    core_api=core_api,
                    apps_api=apps_api,
                    namespace=self.namespace,
                )

        for yaml in self._yamls:
            utils.create_from_yaml(
                k8s_client,
                yaml_file=yaml,
                apply=True,
                namespace=self.namespace,
            )


# ---------
# elementary resources


class Secret(Component):
    """
    Provide a `Secret` resource which provisions secret data on the kubernetes cluster.
    This component is intended to be used with the `batou_ext.kubernetes.Kubernetes` component.

    As for what kind of secret types there are please consult https://kubernetes.io/docs/concepts/configuration/secret/#secret-types.

    Do note that kubernetes does not support nested secrets or a list of values and instead requires all values are simple strings that can be base64 encoded.

    Use a `kubernetes.SecretPurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.Secret("testsecret", data={"this": "is", "an": "example"})
    ```
    """

    namevar = "name"

    type = Attribute(str, "Opaque")
    data = Attribute(dict, {})

    _override = Attribute(dict, {})
    _priority = 1000
    _required_params_ = {
        "data": {"test": "data"},
    }

    def configure(self):
        assert all(map(lambda val: isinstance(val, str), self.data.values()))

        b64_data = {key: b64(value) for key, value in self.data.items()}

        self.path = f"secret-{self.name}.yaml"
        self += YAMLContent(
            self.path,
            data={
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": self.name},
                "type": self.type,
                "data": b64_data,
            },
            override=self._override,
        )

        self.path = self.map(self.path)
        self.provide("k3s-provider", self)


class ConfigMap(Component):
    """
    Provide a `ConfigMap` resource which provisions configuration data on the kubernetes cluster.
    This component is intended to be used with the `batou_ext.kubernetes.Kubernetes` component.

    Do note that kubernetes does not support nested configuration or a list of values and instead requires all values are simple strings that can be base64 encoded.

    Use a `kubernetes.ConfigMapPurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.ConfigMap("testconfiguration", data={"this": "is", "an": "example"})
    ```
    """

    namevar = "name"
    data = Attribute(dict, {})

    _override = Attribute(dict, {})
    _priority = 900
    _required_params_ = {
        "data": {"test": "data"},
    }

    def configure(self):
        assert all(map(lambda val: isinstance(val, str), self.data.values()))

        self.path = f"configmap-{self.name}.yaml"
        self += YAMLContent(
            self.path,
            data={
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": self.name},
                "data": self.data,
            },
            override=self._override,
        )

        self.path = self.map(self.path)
        self.provide("k3s-provider", self)


class PersistentVolume(Component):
    """
    Provide a `PersistentVolume` resource which provisions a persistent volume on the kubernetes cluster.
    This component is intended to be used with the `batou_ext.kubernetes.Kubernetes` component.

    If you use this component you probably also want to use a `kubernetes.PersistentVolumeClaim`.

    Use a `kubernetes.PersistentVolumePurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.PersistentVolume("testpv", dir="/var/lib/testpv", capacity="10Gi")
    self += kubernetes.PersistentVolumeClaim("testpvc", capacity="10Gi")
    ```
    """

    namevar = "name"

    dir = Attribute(str)
    capacity = Attribute(str, "10Gi")

    _override = Attribute(dict, {})
    _priority = 800

    _required_params_ = {
        "dir": "/tmp",
    }

    def configure(self):
        self += Directory(self.dir)
        self.localpath = self._.path

        self.path = f"pv-{self.name}.yaml"

        self += YAMLContent(
            self.path,
            data={
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "metadata": {"name": self.name},
                "spec": {
                    "capacity": {"storage": self.capacity},
                    "volumeMode": "Filesystem",
                    "accessModes": ["ReadWriteOnce"],
                    "persistentVolumeReclaimPolicy": "Delete",
                    "storageClassName": "local-storage",
                    "local": {"path": self.localpath},
                    "nodeAffinity": {
                        "required": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "kubernetes.io/hostname",
                                            "operator": "In",
                                            # allow pods that require this volume to run on all hosts
                                            "values": [
                                                (
                                                    host
                                                    if isinstance(host, str)
                                                    else host._name
                                                )
                                                for host in self.environment.hosts
                                            ],
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                },
            },
            override=self._override,
        )

        self.path = self.map(self.path)
        self.provide("k3s-provider", self)


class PersistentVolumeClaim(Component):
    """
    Provide a `PersistentVolumeClaim` resource which provisions a volume claim on the kubernetes cluster.
    This component is intended to be used with the `batou_ext.kubernetes.Kubernetes` component.

    If you use this component you probably also want to use a `kubernetes.PersistentVolume` to that it can be claimed.

    Use a `kubernetes.PersistentVolumeClaimPurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.PersistentVolume("testpv", dir="/var/lib/testpv", capacity="10Gi")
    self += kubernetes.PersistentVolumeClaim("testpvc", capacity="10Gi")
    ```
    """

    namevar = "name"
    capacity = Attribute(str, "10Gi")

    _override = Attribute(dict, {})
    _priority = 700

    def configure(self):
        self.path = f"pvc-{self.name}.yaml"

        self += YAMLContent(
            self.path,
            data={
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": self.name},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "volumeMode": "Filesystem",
                    "resources": {"requests": {"storage": self.capacity}},
                    "storageClassName": "local-storage",
                },
            },
            override=self._override,
        )

        self.path = self.map(self.path)
        self.provide("k3s-provider", self)


class Deployment(Component):
    """
    Provide a `Deployment` resource which provisions a deployment on the kubernetes cluster.
    This component is intended to be used with the `batou_ext.kubernetes.Kubernetes` component.

    Use a `kubernetes.DeploymentPurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.PersistentVolumeClaim("testpvc", capacity="10Gi")
    volume = self._

    self += kubernetes.Deployment(
        "nginx",
        image="nginx:stable-alpine",
        port=80,
        replicas=5,
        pvcs={volume.name: "/somewhere/in/the/pod"},
    )
    ```
    """

    namevar = "name"
    container_name = Attribute(str, None)
    image = Attribute(str)
    port = Attribute(int)
    replicas = Attribute(int, 1)

    pvcs = Attribute(dict, {})
    secrets = Attribute(list, [])
    configmaps = Attribute(list, [])
    registry_secret = Attribute(Secret, None)

    _override = Attribute(dict, {})
    _priority = 600

    _required_params_ = {
        "image": "testimage",
        "port": 8080,
    }

    def configure(self):
        if not self.container_name:
            self.container_name = self.name

        self.path = f"deployment-{self.name}.yaml"
        yaml_data = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": self.name},
            "spec": {
                "replicas": self.replicas,
                "selector": {"matchLabels": {"name": self.name}},
                "template": {
                    "metadata": {"labels": {"name": self.name}},
                    "spec": {
                        "containers": [
                            {
                                "name": self.container_name,
                                "image": self.image,
                                "ports": [{"containerPort": self.port}],
                                "envFrom": [
                                    {"secretRef": {"name": sref}}
                                    for sref in self.secrets
                                ]
                                + [
                                    {"configMapRef": {"name": cmref}}
                                    for cmref in self.configmaps
                                ],
                                "volumeMounts": [
                                    {
                                        "name": f"volume-{pvc_name}",
                                        "mountPath": mountPath,
                                    }
                                    for pvc_name, mountPath in self.pvcs.items()
                                ],
                            }
                        ],
                        "volumes": [
                            {
                                "name": f"volume-{pvc_name}",
                                "persistentVolumeClaim": {"claimName": pvc_name},
                            }
                            for pvc_name, mountPath in self.pvcs.items()
                        ],
                    },
                },
            },
        }

        if self.registry_secret:
            yaml_data["spec"]["template"]["spec"]["imagePullSecrets"] = [
                {"name": self.registry_secret.name}
            ]

        self += YAMLContent(
            self.path,
            data=yaml_data,
            override=self._override,
        )

        self.path = self.map(self.path)
        self.provide("k3s-provider", self)


class Service(Component):
    """
    Provide a `Service` resource which provisions a service on the kubernetes cluster.
    This component is intended to be used with the `batou_ext.kubernetes.Kubernetes` component.

    Use a `kubernetes.ServicePurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.Deployment(
        "nginx",
        image="nginx:stable-alpine",
        port=80,
        replicas=5,
        pvcs={volume.name: "/somewhere/in/the/pod"},
    )
    deployment = self._

    self += kubernetes.Service("nginx", deployment=deployment.name, port=65000, target_port=deployment.port)
    ```
    """

    namevar = "name"
    deployment = Attribute(str)
    port = Attribute(int)
    target_port = Attribute(int)

    _override = Attribute(dict, {})
    _priority = 500

    _required_params_ = {
        "deployment": "testdeployment",
        "port": 12345,
        "target_port": 80,
    }

    def configure(self):
        assert self.deployment

        if not self.target_port:
            self.target_port = self.deployment.port
        if not self.port:
            self.port = self.target_port

        self.path = f"service-{self.name}.yaml"

        yaml_data = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": self.name},
            "spec": {
                "ports": [
                    {
                        "port": self.port,
                        "targetPort": self.target_port,
                    }
                ],
                "selector": {"name": self.deployment},
            },
        }

        if address := self.require_one("k3s-address", strict=False):
            yaml_data["spec"]["externalIPs"] = [address.listen.host]

        self += YAMLContent(
            self.path,
            data=yaml_data,
            override=self._override,
        )

        self.path = self.map(self.path)
        self.provide("k3s-provider", self)


# ---------------
# compound resources don't need a priority since they are made up of other resources


class Volume(Component):
    """
    A compound resource that provisions both a persistent volume (kubernetes.PersistentVolume)
    as well as a claim (kubernetes.PersistentVolumeClaim) for the entire volume

    Use a `kubernetes.VolumePurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.Volume(
        "testvolume",
        dir="/var/lib/testvolume"
    )
    ```
    """

    namevar = "name"
    capacity = Attribute(str, "10Gi")
    dir = Attribute(str)

    _required_params_ = {"dir": "/tmp"}

    def configure(self):
        self += PersistentVolume(self.name, dir=self.dir, capacity=self.capacity)
        self += PersistentVolumeClaim(self.name, capacity=self.capacity)


class RegistrySecret(Component):
    """
    A wrapper around the kubernetes.Secret class that makes provisioning registry secrets a lot simpler.

    Use a `kubernetes.SecretPurge` to deprovision this resource.

    Usage example:
    ```
    self += kubernetes.RegistrySecret(
        "testregistry",
        url="https://testhub.my.domain/api/v1/",
        username="admin",
        password="hunter2"
    )
    ```
    """

    namevar = "name"
    username = Attribute(str)
    password = Attribute(str)
    url = Attribute(str)

    _required_params_ = {
        "username": "test123",
        "password": "hunter2",
        "url": "test.registry.does.not.exist",
    }

    def configure(self):
        auth = b64(f"{self.username}:{self.password}")
        configjson = json.dumps({"auths": {self.url: {"auth": auth}}})

        self += Secret(
            self.name,
            type="kubernetes.io/dockerconfigjson",
            data={".dockerconfigjson": configjson},
        )


# --------------------------------
# purges


class ServicePurge(Component):
    """
    Provide a way to purge previously provisioned secrets.

    Usage example:
    ```
    self += kubernetes.ServicePurge("testservice")
    ```
    """

    namevar = "name"
    _priority = 600

    def configure(self):
        self.path = f"service-{self.name}.yaml"
        self.provide("k3s-purger", self)

    def purge(self, *, core_api, namespace):
        try:
            core_api.delete_namespaced_service(
                name=self.name,
                namespace=namespace,
            )
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Unknown error: {e}")
                raise RuntimeError(e)
            else:
                self.log(f"could not find service to delete: `{self.name}`")


class DeploymentPurge(Component):
    """
    Provide a way to purge previously provisioned deployments.

    Usage example:
    ```
    self += kubernetes.DeploymentPurge("testdeployment")
    ```
    """

    namevar = "name"
    _priority = 500

    def configure(self):
        self.path = f"deployment-{self.name}.yaml"
        self.provide("k3s-purger", self)

    def purge(self, *, apps_api, namespace):
        try:
            apps_api.delete_namespaced_deployment(
                name=self.name,
                namespace=namespace,
            )
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Unknown error: {e}")
                raise RuntimeError(e)
            else:
                self.log(f"could not find deployment to delete: `{self.name}`")


class SecretPurge(Component):
    """
    Provide a way to purge previously provisioned secrets.

    Usage example:
    ```
    self += kubernetes.SecretPurge("testsecret")
    ```
    """

    namevar = "name"
    _priority = 400

    def configure(self):
        self.path = f"secret-{self.name}.yaml"
        self.provide("k3s-purger", self)

    def purge(self, *, core_api: client.CoreV1Api, namespace):
        try:
            # TODO
            core_api.delete_namespaced_secret(name=self.name, namspace=namespace)
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Unknown error: {e}")
                raise RuntimeError(e)
            else:
                self.log(f"could not find secret to delete: `{self.name}`")


class ConfigMapPurge(Component):
    """
    Provide a way to purge previously provisioned ConfigMaps.

    Usage example:
    ```
    self += kubernetes.ConfigMapPurge("testconfigmap")
    ```
    """

    namevar = "name"
    _priority = 300

    def configure(self):
        self.path = f"configmap-{self.name}.yaml"
        self.provide("k3s-purger", self)

    def purge(self, *, core_api: client.CoreV1Api, namespace):
        try:
            core_api.delete_namespaced_config_map(name=self.name, namespace=namespace)
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Unknown error: {e}")
                raise RuntimeError(e)
            else:
                self.log(f"could not find configmap to delete: `{self.name}`")


class PersistentVolumeClaimPurge(Component):
    """
    Provide a way to purge previously provisioned Persistent Volume Claims.

    Usage example:
    ```
    self += kubernetes.PersistentVolumeClaimPurge("testpvc")
    ```
    """

    namevar = "name"
    _priority = 200

    def configure(self):
        self.path = f"pvc-{self.name}.yaml"
        self.provide("k3s-purger", self)

    def purge(self, *, core_api: client.CoreV1Api, namespace):
        try:
            core_api.delete_namespaced_persistent_volume_claim(
                name=self.name,
                namespace=namespace,
            )
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Unknown error: {e}")
                raise RuntimeError(e)
            else:
                self.log(f"could not find pvc to delete: `{self.name}`")


class PersistentVolumePurge(Component):
    """
    Provide a way to purge previously provisioned Persistent Volumes.

    Usage example:
    ```
    self += kubernetes.PersistentVolumePurge("testpv")
    ```
    """

    namevar = "name"
    _priority = 100

    def configure(self):
        self.path = f"pvc-{self.name}.yaml"
        self.provide("k3s-purger", self)

    def purge(
        self,
        *,
        core_api: client.CoreV1Api,
        namespace,
    ):
        try:
            core_api.delete_persistent_volume(
                name=self.name,
            )
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Unknown error: {e}")
                raise RuntimeError(e)
            else:
                self.log(f"could not find pvc to delete: `{self.name}`")


class VolumePurge(Component):
    """
    Provide a way to purge previously provisioned Volumes.

    Usage example:
    ```
    self += kubernetes.VolumePurge("testvolume")
    ```
    """

    namevar = "name"

    def configure(self):
        self += PersistentVolumePurge(self.name)
        self += PersistentVolumeClaimPurge(self.name)
