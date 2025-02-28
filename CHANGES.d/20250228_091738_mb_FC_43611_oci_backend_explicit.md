- `batou_ext.oci.Container`: set `backend` explicitly in Nix expression.

  Otherwise this depends on the state version having varying results depending on whether
  the machine was installed with a NixOS older or newer than 22.05.
