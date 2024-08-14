{ lib, pkgs, ... }: {
  systemd.services.mailpit = {
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      DynamicUser = true;
      StateDirectory = "mailpit";
      WorkingDirectory = "%S/mailpit";
      ExecStart = "${lib.getExe pkgs.mailpit} -d mailpit.db -s \"[::]:{{component.smtp_port}}\" -l \"[::1]:{{component.ui_port}}\" --max {{component.max}}";
      Restart = "on-failure";
    };
  };

  flyingcircus.services.nginx.virtualHosts."{{ component.public_name }}" = {
    forceSSL = true;
    enableACME = true;
    basicAuthFile = "{{component.http_auth.path}}";
    locations."/" = {
      proxyPass = "http://[::1]:8025";
      proxyWebsockets = true;
    };
  };
}
