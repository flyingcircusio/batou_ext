let
  # see https://nixos.org/channels/
  nixpkgs = fetchTarball {{component.channel}};

in
{ pkgs ? import nixpkgs { } }:

with pkgs;
let

  shellInit = writeText "shellInit"''

    {{component.shellInit.replace('\n', '\n    ').strip()}}
  '';

  {{component.let_extra}}

in buildEnv {
    name = "{{ '{{' }}component.nix_env_name{{ '}}' }}";
    paths = [
      (runCommand "profile" { } "install -D ${shellInit} $out/etc/profile.d/{{component.profile_name}}.sh")
      {%- for name in component.packages %}
      {{name}}
      {%- endfor %}
    ];
    extraOutputsToInstall = [ "bin" "dev" "lib" "man" "out" ];
}
