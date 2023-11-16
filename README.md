# batou_ext - a library of components for batou

`batou_ext` master is now supporting Python3 and is depending on batou2. If you still want to use batou_ext with batou 1.x running Python2 you still can use the [batou1-py2](https://github.com/flyingcircusio/batou_ext/tree/batou1-py2) branch.

To add `batou_ext` to your deployment, add a like to the `requirements.txt` of your batou deployment::

```
batou_ext>=2.4
```

## Development and release process

* Changes should be accompanied with a changelog entry. Use `./changelog.sh` to create one.

* Releasing will create a tag and publishes the package to pypi. Use `./release-this.sh` to create a release.
