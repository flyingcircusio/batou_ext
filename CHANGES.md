
## 2.4.5 (2024-04-17)


- add an option to move mailhog log output (`stdout` + `stderr`) to a different namespace, e.g. "mailhog". see systemd.exec(5) for more information
- add an option to disable `stdout` logging for the mailhog service

- improve dectection of a versions file for versions updates

- fix the oci.Container verify method not throwing an updaterequired on changes to the docker container's environment file

Add systemd-run async cleanup option for SymlinkAndCleanup removals


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
