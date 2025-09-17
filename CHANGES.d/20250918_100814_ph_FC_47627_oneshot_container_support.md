- Add a configuration option to the batou_ext.oci.Container component that marks the container as a "oneshot" unit indicating that it should not be restarted when shutting down.

  This is particularly useful for containers that run some one-off task like database migrations or other scheduled tasks.
