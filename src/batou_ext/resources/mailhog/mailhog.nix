{ pkgs, lib, ... }:
{
  services.mailhog = {
    enable = true;
    apiPort = {{component.apiport}};
    smtpPort = {{component.mailport}};
    uiPort = {{component.uiport}};
    storage = "{{component.storage_engine}}";
  };

  flyingcircus.services.nginx.virtualHosts = {
    "{{component.public_name}}" = {
      forceSSL = true;
      enableACME = true;
      {% if component.http_auth_enable %}
      basicAuthFile = "{{component.http_auth.path}}";
      {% endif %}
      locations = {
        "/" = {
          proxyPass = "http://localhost:{{component.uiport}}";
          extraConfig = ''
            proxy_connect_timeout 24000s;
            proxy_read_timeout 24000s;
            proxy_send_timeout 24000s;
            chunked_transfer_encoding on;
            proxy_set_header X-NginX-Proxy true;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_http_version 1.1;
            proxy_redirect off;
            proxy_buffering off;
          '';
        };
      };
    };
  };
}
