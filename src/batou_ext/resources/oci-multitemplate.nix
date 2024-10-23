{lib, ...}: {
  config = lib.mkMerge [
    # {% for container in component.containers %}
    {
      # {% if container.monitor %}
      flyingcircus = {
        services.sensu-client.checks."docker-{{container.container_name}}" = {
          notification = "Status of container {{container.container_name}}";
          command = ''
            if $(systemctl is-active --quiet docker-{{container.container_name}}); then
              echo "docker container {{container.container_name}} is ok"
            else
              echo "docker container {{container.container_name}} is inactive"
              exit 2
            fi
          '';
        };
      };
      # {% endif %}

      virtualisation.oci-containers = {
        backend = "docker";
        containers."{{container.container_name}}" = {
          # {% if container.entrypoint %}
          entrypoint = "{{container.entrypoint}}";
          # {% endif %}

          # {% if container.docker_cmd %}
          cmd = [
            # {% for cmd in container._docker_cmd_list %}
            "{{cmd}}"
            # {% endfor %}
          ];
          # {% endif %}

          login = {
            # {% if container.registry_address %}
            registry = "{{container.registry_address}}";
            # {% endif %}

            # {% if container.registry_user and container.registry_password %}
            username = "{{container.registry_user}}";
            passwordFile = "{{container.password_file.path}}";
            # {% endif %}
          };

          extraOptions = [
            "--pull=always"
            # {% for option in (container.extra_options or []) | sort %}
            "{{option}}"
            # {% endfor %}
          ];

          volumes = [
            # {% for key, value in container.mounts.items() | sort  %}
            "{{key}}:{{value}}"
            # {% endfor %}
          ];

          image = "{{container.image}}:{{container.version}}";
          environmentFiles = ["{{container.envfile.path}}"];

          ports = [
            # {% for key, value in container.ports.items() | sort  %}
            "{{key}}:{{value}}"
            # {% endfor %}
          ];

          dependsOn = [
            # {% for value in container.depends_on | sort %}
            "{{value}}"
            # {% endfor %}
          ];
        };
      };
    }
    # {% endfor %}
  ];
}
