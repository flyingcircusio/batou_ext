{ config, lib, pkgs, ... }:

let
  script =
    # {% if component.predefined_service %}
    (pkgs.writeShellScript
      "{{ component.service }}-start"
      config.systemd.services."{{ component.service }}".script)
    # {% else %}
    "{{ component.script }}"
    # {% endif %}
    ;
in {
  # {% if component.predefined_service %}
  assertions = [
    { assertion = config.systemd.services."{{ component.service }}".script != "";
      message = "Service {{ component.service }} needs to have `script` set!";
    }
  ];
  # {% endif %}

  systemd.services."{{ component.service }}" = {
    path = [
      config.systemd.package
      # interpreter for the watchdog script
      (pkgs.python3.withPackages (ps: with ps; [
        requests
      ]))
    ];
    serviceConfig = {
      Type = "notify";
      # Allow child processes of ExecStart
      # to do `sd_notify(3)`.
      NotifyAccess = "all";
      Restart = "always";
      TimeoutStartSec = lib.mkForce "{{ component.start_timeout }}";
      WatchdogSec = "{{ component.watchdog_interval }}";

      ExecStart = lib.mkForce (pkgs.writeShellScript "watchdog-{{ component.service }}" ''
        exec {{ component.watchdog_script_path }} \
          --healthcheck-url {{ component.healthcheck_url }} \
          --healthcheck-timeout {{ component.healthcheck_timeout }} \
          --watcher-loglevel info \
          --startup-check-interval {{ component.startup_check_interval }} \
          --check-interval {{ component.check_interval }} \
          -- ${script}
      '');
    };
  };
}
