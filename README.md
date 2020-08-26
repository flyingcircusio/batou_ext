# batou_ext - a library of components for batou

`batou_ext` master is now supporting Python3 and is depending on batou2. If you still want to use batou_ext with batou 1.x running Python2 you still can use the [batou1-py2](https://github.com/flyingcircusio/batou_ext/tree/batou1-py2) branch.

To add `batou_ext` to your deployment, add a like to the `requirements.txt` of your batou deployment::

```
git+git://github.com/flyingcircusio/batou_ext.git@XXX#egg=batou_ext
```

(Replace XXX by the revision you want to use. Please keep in mind, that using HEAD or master will result potential in not reproducable deployments)


Another option is to use the zip provided by github:

```
batou_ext @ https://github.com/flyingcircusio/batou_ext/archive/xxx.zip#sha256=8yyy
```

(Replace XXX and YYY with the actual revision and checksum)

Which is adding some more safety by using the hash as well as should be faster in most cases instead of cloning the repository. This entry for `requirements.txt` can be created by calling the `bin/update_batouext` script from your batou_ext checkout.


Note that there needs to be a fixed revision (e.g. ``ea0073d08bda``). This has two reasons:

1. You *really* want the deployment to be repeatable. If you just use ``HEAD`` you never know what you'll get.

2. Updating is not stable. If you don't specify a revision, any is fine. You will end up with different revisions on different hosts.
