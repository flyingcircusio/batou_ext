
## 2.4.26 (2025-02-28)


- `batou_ext.oci.Container`: set `backend` explicitly in Nix expression.

  Otherwise this depends on the state version having varying results depending on whether
  the machine was installed with a NixOS older or newer than 22.05.


## 2.4.25 (2025-02-21)


- `batou_ext.oci.Container`: allow to use `podman` as backend instead of `docker`.
  This also enables the following features:

  * Rootless containers: by setting the `user` option to a different user. By default,
    the service user of the deployment is used.

  * Only mark services as `active` if the container is up. This requires that the
    container has a healthcheck. Alternatively, a healthcheck can be configured
    with the health_cmd attribute.


## 2.4.24 (2025-02-17)


- `batou_ext.file.SymlinkAndCleanup`: add option `etag_suffix`.
  This contains a suffix that each symlinked file may have.

  For instance, when doing `SymlinkAndCleanup` on a file downloaded with
  `batou_ext.s3.Download`, the pattern `*.tar.gz` doesn't clean up the
  `.etag` files. However, `*.tar.gz*` (or an equivalent) would also remove
  the etag files of the files that are symlinked to `current` & `last`.


## 2.4.23 (2025-01-07)


- Fix using multiple DeploymentTrash Component on a single host breaking the Nix rebuild, especially across different deployments to the same machine.
  This was because the values for the IOPS read and write Limits in the Systemd serviceConfig attribute set were defined as strings (which cannot be merged unless identical) instead of lists (which can always be merged).


## 2.4.22 (2024-12-27)


- Allow to configure the name of the `.nix` file created by `batou_ext.file.DeploymentTrash`.


## 2.4.21 (2024-12-13)


- Fix interactive version select.

- Change the releaser defaults to actually release


## 2.4.20 (2024-12-10)


- Correctness fix for `jenkins set-version`: if a tag is resolved, make sure it's _always_
  resolved to the rev of the tagged commit (instead of the tag's rev) or fail hard to avoid
  incorrect revs.

- Improve documentation of `batou_ext.file.DeploymentTrash`


## 2.4.19 (2024-11-28)


- make the DeploymentTrash's trash directory configurable and output a potentially helpful message on OSErrors which could indicate that the trash directory and the directory that is being trashed are on different devices


## 2.4.18 (2024-11-15)


- nixos.NixOSModule: Mark generated context file as sensitive (Fixes #167)

- add an env argument for the `Run` component to support running commands with specific environment variables

- The component `batou_ext.python.FixELFRunPath` now uses a patched version of patchelf to make sure that the
  dynamic libraries don't get larger per deploy.

  When a certain threshold is exceeded, Python will fail to import these.

  If the component got regularly executed in deployments, you may want to consider recreating
  the virtualenv once.


## 2.4.17 (2024-10-28)


- A new component `batou_ext.systemd.ScalableService` has been added. This provides configurations
  for a service that can exist multiple times (e.g. queue consumers). Detailed usage instructions
  and further information can be found in the component's docstring.


## 2.4.16 (2024-09-11)


- A new component `batou_ext.mail.Mailpit` has been added.
  Mailpit is an alternative for Mailhog which is not maintained anymore.

- fix a mysterious regression that cause a test to fail

- redis.Redis: Allow to set provide name

* The `SymlinkAndCleanup` internally uses the `DeploymentTrash` component internally which
  deletes old code using `systemd-tmpfiles` and throttles the operation with `IOReadIOPSMax`
  and `IOWriteIOPSMax`.

  This didn't have any effect before because these settings were wrongly placed in `[Unit]`
  instead of `[Service]`.


## 2.4.15 (2024-08-26)


- fix a regression in the versions update script where the environment was not loaded correctly


## 2.4.14 (2024-08-12)


- `ssl.Certificate`: Set proper ACL for non-let's encrypt certificates.


## 2.4.13 (2024-08-12)


- Fix setting acl for `ssl.Certificate` during ceritificate renewal.


## 2.4.12 (2024-08-12)


- Set correct acl for `ssl.Certificates` on certificate renew.


## 2.4.11 (2024-08-09)


- `oci.Container`: Add option to disable OCI container monitoring.

  This is mainly useful for containers which are not running all the time.

- `oci.Container`: make rebuild optional

  This is useful, when there are multiple container deployed which should be activated at once.

- Fix a bug in the version update script where multiple environments sharing the same branch would not be updated correctly

- the `SymlinkAndCleanup` component was adjusted to clean up asynchronously using systemd's tmpfiles instead of deleting all candidates immediately


## 2.4.10 (2024-06-11)


- oci.Container: Fix a bug where containers were not restarted properly even though their image digest was out of sync after the remote tag has been updated

- oci.Container: Fix a typo in the oci container component's verify method


## 2.4.9 (2024-06-04)


- `batou_ext.python.FixELFRunPath`: search not only `env_directory`, but also its subdirs for C libraries needed by the libraries to patch.

- Fix `PurgePackage` raising error when package is not found.

- The attribute `public_smtp_name` of `batou_ext.mail.Mailhog` now has a default value. It points to `self.host.fqdn`.

- adjust the certificate expiry check output to be more easily parseable


## 2.4.8 (2024-05-08)


- systemd timers: add an option to enable persistence
  breaking change: systemd timers are now non-persistent by default.
  The previous default behaviour was a problem for cronjobs that should
  not be started immediately following a reboot / downtime

* Added a component `batou_ext.python.FixELFRunPath` which modifies `DT_RUNPATH` & `DT_RPATH` of `.so`-files in a venv to load the correct libraries (from either a Nix env or other Python libraries). Please read the docstring carefully before using it.

- OCI: cache validation result during deployment.

  Caching results speeds up deployments where multiple containers with the same image are deployed.


## 2.4.7 (2024-04-29)


* Added component `batou_ext.http.HTTPServiceWatchdog` that adds a check to a systemd unit
  whether a given URL is reachable (e.g. a `/health` endpoint). If the URL cannot be reached within
  a certain interval, the service will be restarted. Further details are documented in the
  docstring.

- Fix `SymlinkAndCleanup` async delete and allow custom extra arguments to `systemd run`.


## 2.4.6 (2024-04-23)


- OCI: Support registries where the docker login is different than the registry used in referencing containers.

- OCI: Improve change detection of remote images (required for docker.io)

- OCI: The nix file does not contain sensitive data, so don’t mark it as such.

- OCI: add support for extraOptions

* Added a script `s3_bootstrap` that interactively creates an S3 bucket (including a radosgw account & keys if needed). Will be installed with `batou_ext` if the `s3-bootstrap` extra is requested.


## 2.4.5 (2024-04-17)


- add an option to move mailhog log output (`stdout` + `stderr`) to a different namespace, e.g. "mailhog". see systemd.exec(5) for more information

- add an option to disable `stdout` logging for the mailhog service

- improve dectection of a versions file for versions updates

- fix the oci.Container verify method not throwing an updaterequired on changes to the docker container's environment file

- Add systemd-run async cleanup option for SymlinkAndCleanup removals


## 2.4.4 (2024-04-05)


- Change the behaviour of the batou_ext.versions updater to allow environments to share a branch

* Added a component `batou_ext.git.Remote` which allows to manipulate remotes of a git repository.


## 2.4.3 (2024-01-17)


- Improve output handling for the `PurgePackage` component. Will not appear like a fatal error in logs anymore when the package has been purged already or is not installed for another reason


## 2.4.2 (2023-12-08)


* Make it possible to add arbitrary additional configuration to a service created by a `SystemdTimer()`.

* Add `nixos.NixOSModule` to inject component attributes into .nix files.


## 2.4.1 (2023-11-16)


* Add `*.md` to the release, so it can actually be used.


## 2.4.0 (2023-11-16)

- Add release process with changelog (FC-33250).
