# batou_ext - a library of components for batou

To add `batou_ext` to your deployment, add a like to the `requirements.txt` of your batou deployment::

```
   git+git://github.com/flyingcircusio/batou_ext.git@9ba0ad46576c3f23cedc6271bcd2a25d8572bb33#egg=batou_ext
```

Note that there needs to be a fixed revision (e.g. ``ea0073d08bda``). This has two reasons:

1. You *really* want the deployment to be repeatable. If you just use ``HEAD`` you never know what you'll get.

2. Updating is not stable. If you don't specify a revision, any is fine. You will end up with different revisions on different hosts.
