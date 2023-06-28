{ ... }: {
  flyingcircus = {
    services.sensu-client.checks."docker-{{component.container_name}}" = {
      notification = "Status of container {{component.container_name}}";
      command = ''
        if $(systemctl is-active --quiet docker-{{component.container_name}}); then
          echo "docker container {{component.container_name}} is ok"
        else
          echo "docker container {{component.container_name}} is inactive"
          exit 2
        fi
      '';
    };
  };


  virtualisation.oci-containers = {
    backend = "docker";
    containers."{{component.container_name}}" = {
      # {% if component.entrypoint != None %}
      entrypoint = "{{component.entrypoint}}";
      # {% endif %}

      # {% if component.registry_address %}
      login = {
        registry = "{{component.registry_address}}";

        # {% if component.registry_user and component.registry_password %}
        username = "{{component.registry_user}}";
        passwordFile = "{{component.password_file.path}}";
        # {% endif %}
      };
      # {% endif %}

      extraOptions = [ "--pull=always" ];

      volumes = [
      # {% for key, value in component.mounts.items() | sort  %}
        "{{key}}:{{value}}"
      # {% endfor %}
      ];

      image = "{{component.image}}";
      environmentFiles = [ {{component.envfile.path}} ];

      ports = [
      # {% for key, value in component.ports.items() | sort  %}
        "{{key}}:{{value}}"
      # {% endfor %}
      ];
    };
  };
}
