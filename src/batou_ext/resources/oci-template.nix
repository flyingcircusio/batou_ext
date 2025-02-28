{ ... }:
{
  # {% if component.monitor %}
  flyingcircus = {
    services.sensu-client.checks."{{ component.backend }}-{{component.container_name}}" = {
      notification = "Status of container {{component.container_name}}";
      command = ''
        if $(systemctl is-active --quiet {{ component.backend }}-{{component.container_name}}); then
          echo "{{ component.backend }} container {{component.container_name}} is ok"
        else
          echo "{{ component.backend }} container {{component.container_name}} is inactive"
          exit 2
        fi
      '';
    };
  };
  # {% endif %}

  virtualisation.oci-containers = {
    backend = "{{ component.backend }}";
    containers."{{component.container_name}}" = {
      # {% if component.entrypoint %}
      entrypoint = "{{component.entrypoint}}";
      # {% endif %}

      # {% if component.docker_cmd %}
      cmd = [ {% for cmd in component._docker_cmd_list %} "{{cmd}}" {% endfor %} ];
      # {% endif %}

      login = {
        # {% if component.registry_address %}
        registry = "{{component.registry_address}}";
        # {% endif %}

        # {% if component.registry_user and component.registry_password %}
        username = "{{component.registry_user}}";
        passwordFile = "{{component.password_file.path}}";
        # {% endif %}
      };

      extraOptions = [
        "--pull=always"
        # {% if component.backend == "podman" %}
        "--cgroups=enabled"
        "--cidfile=/run/{{component.container_name}}/ctr-id"
        # {% endif %}
        # {% for option in (component.extra_options or []) %}
        "{{option}}"
        # {% endfor %}
        # {% if component.backend == "podman" %}
        "--sdnotify=healthy"
        # {% endif %}
        # {% if component.health_cmd %}
        "--health-cmd"
        {{ component.health_cmd }}
        # {% endif %}
      ];

      volumes = [
      # {% for key, value in component.mounts.items() | sort  %}
        "{{key}}:{{value}}"
      # {% endfor %}
      ];

      image = "{{component.image}}:{{component.version}}";
      environmentFiles = [ {{component.envfile.path}} ];

      ports = [
      # {% for key, value in component.ports.items() | sort  %}
        "{{key}}:{{value}}"
      # {% endfor %}
      ];

      dependsOn = [
      # {% for value in component.depends_on  %}
        "{{value}}"
      # {% endfor %}

      ];
    };
  };

  # {% if component.backend == "podman" %}
  systemd.services."podman-{{ component.container_name }}".serviceConfig = {
    User = "{{ component.user }}";
    RuntimeDirectory = "{{component.container_name}}";
    Delegate = true;
    NotifyAccess = "all";
  };

  systemd.services."podman-{{ component.container_name }}".wants = [ "linger-users.service" ];
  users.users."{{ component.user }}".linger = true;
  # {% endif %}
}
