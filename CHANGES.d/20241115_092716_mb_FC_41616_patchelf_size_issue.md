- The component `batou_ext.python.FixELFRunPath` now uses a patched version of patchelf to make sure that the
  dynamic libraries don't get larger per deploy.

  When a certain threshold is exceeded, Python will fail to import these.

  If the component got regularly executed in deployments, you may want to consider recreating
  the virtualenv once.
