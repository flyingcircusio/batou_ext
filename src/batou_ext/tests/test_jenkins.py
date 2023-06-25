from textwrap import dedent
from unittest import mock

import batou_ext.jenkins


def test_set_versions_git_mode(tmpdir):
    ini = tmpdir / "versions.ini"
    ini.write_text(
        dedent(
            """
                       [prog1]
                       # defaults to git-resolve for bw compat
                       url = git://prog1

                       [prog2]
                       url = http://prog2
                       update = git-resolve
                   """
        ),
        encoding="UTF-8",
    )

    with mock.patch("batou_ext.jenkins.git_resolve") as git_resolve:
        git_resolve.return_value = "abcdef"
        batou_ext.jenkins.set_versions(
            str(ini), '{"prog1": "a-tag", "prog2": ""}'
        )

    assert (
        dedent(
            """\
        [prog1]
        url = git://prog1
        revision = abcdef
        version = a-tag

        [prog2]
        url = http://prog2
        update = git-resolve
    """
        )
        == ini.read_text(encoding="UTF-8")
    )


def test_simple_value_update_mode(tmpdir):
    ini = tmpdir / "versions.ini"
    ini.write_text(
        dedent(
            """
                          [prog1]
                          version = 1.0
                          update = pass:version

                          [prog2]
                          url = http://prog2
                          update = pass:url
            """
        ),
        encoding="UTF-8",
    )
    batou_ext.jenkins.set_versions(
        str(ini), '{"prog1": "1.2", "prog2": "http://foobar"}'
    )
    assert (
        dedent(
            """\
      [prog1]
      version = 1.2
      update = pass:version

      [prog2]
      url = http://foobar
      update = pass:url
    """
        )
        == ini.read_text(encoding="UTF-8")
    )
