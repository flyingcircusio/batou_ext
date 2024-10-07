{ lib, ... }:

let
  numRunningInstances = lib.toInt "{{ component.running_instances }}";
  baseName = "{{ component.base_name }}";
in {
  systemd.targets."${baseName}" = {
    wantedBy = [ "multi-user.target" ];
    # If this target is reached (i.e. started), also start
    # {{ component.running_instances }} messenger services.
    wants = lib.genList (n: "${baseName}@${toString n}.service") numRunningInstances;
  };

  systemd.services."${baseName}@" = {
    # If the target stops or gets restarted, also stop/restart this unit.
    partOf = [ "${baseName}.target" ];
  };
}
