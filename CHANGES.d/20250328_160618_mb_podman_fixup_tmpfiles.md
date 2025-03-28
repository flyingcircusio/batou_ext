- oci: make `user@uid.service` wait until all containers have exited and clear `/tmp` of containers.
  Without those, unclean shutdowns were observed that prevented the containers from getting back
  up on a reboot.
