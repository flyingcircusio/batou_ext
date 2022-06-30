{ pkgs, lib, ... }:
{
  flyingcircus.journalbeat.logTargets = {
    {{component.transport_name}} = {
      host = "{{component.graylog_host}}";
        port = {{component.graylog_port}};
      };
  };
}
