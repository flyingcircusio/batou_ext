{ pkgs, ... }: let
  {{component.let_extra}}

in {
  users.users."{{component.environment.service_user}}".packages = with pkgs; [
    # {%- for name in component.packages %}
    {{name}}
    # {%- endfor %}
  ];

  environment.shellInit = ''
    {{component.shellInit.replace('\n', '\n    ').strip()}}
  '';
}
