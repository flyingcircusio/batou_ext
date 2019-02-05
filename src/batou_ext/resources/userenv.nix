let
  # see https://nixos.org/channels/
  nixpkgs = fetchTarball {{component.channel}};

in
{ pkgs ? import nixpkgs { } }:

with pkgs;
let

  shellInit = writeText "shellInit"''
    export LIBRARY_PATH=$HOME/.nix-profile/lib
    export CPATH=$HOME/.nix-profile/include
    export C_INCLUDE_PATH=$CPATH
    export CPLUS_INCLUDE_PATH=$CPATH
    export PKG_CONFIG_PATH=$HOME/.nix-profile/lib/pkgconfig

    {{component.shellInit.replace('\n', '\n    ').strip()}}
  '';

in buildEnv {
    name = "{{ '{{' }}component.nix_env_name{{ '}}' }}";
    paths = [
      (runCommand "profile" { } "install -D ${shellInit} $out/etc/profile.d/{{component.profile_name}}.sh")
      {%- for name in component.packages %}
      {{name}}
      {%- endfor %}
    ];
    extraOutputsToInstall = [ "out" "dev" "bin" "man" ];
}
