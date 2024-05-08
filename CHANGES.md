
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
