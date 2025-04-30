- Added `batou_ext.fcio.Maintenance{Start,End}`: with these components it's possible to mark the RG
  as "in maintenance". Components can be scheduled between these two by doing
  `self.provide("needs-maintenance", self)`.
