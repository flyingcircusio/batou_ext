with import <nixpkgs> {};
with {{component.pythonPackages}};

buildPythonPackage {
  name = "impurePythonEnv";
  buildInputs = [
    {% for pkg in component.nix_packages %}
    {{pkg}}{% endfor %}
    stdenv ];
  src = null;
  # When used as `nix-shell --pure`
  shellHook = ''
    unset http_proxy
    export GIT_SSL_CAINFO=/etc/ssl/certs/ca-bundle.crt
    export pythonEnvLoaded=1
  '';
  # used when building environments
  extraCmds = ''
    unset http_proxy # otherwise downloads will fail ("nodtd.invalid")
    export GIT_SSL_CAINFO=/etc/ssl/certs/ca-bundle.crt
  '';
}
