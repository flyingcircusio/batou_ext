
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
