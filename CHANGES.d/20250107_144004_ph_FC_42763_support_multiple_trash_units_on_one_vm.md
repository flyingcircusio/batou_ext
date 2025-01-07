- Fix using multiple DeploymentTrash Component on a single host breaking the Nix rebuild, especially across different deployments to the same machine.
  This was because the values for the IOPS read and write Limits in the Systemd serviceConfig attribute set were defined as strings (which cannot be merged unless identical) instead of lists (which can always be merged).
