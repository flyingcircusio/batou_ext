{
  buildPythonPackage,
  pyyaml,
  pyaml,
  six,
  src,
  inquirerpy,
  batou,
}:
buildPythonPackage {
  pname = "batou_ext";
  version = "latest";
  propagatedBuildInputs = [pyyaml pyaml six batou inquirerpy];
  inherit src;
}
