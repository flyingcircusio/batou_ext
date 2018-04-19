import batou.component
import batou.lib.file


class Run(batou.component.Component):
    """
    A component taking over a script content, saving it to an actual script
    and running it afterwards.
    Example:

    script_content = '''
    #!/bin/sh
    echo "hello world"
    '''
    self += Run(
        'hello.sh',
        content=script_content)

    The script is called only, if there are any changes at the parent component.
    """
    namevar = 'command'
    content = None

    def configure(self):

        self += batou.lib.file.File(
            self.command,
            content=self.content,
            mode=0o700)
        self.command_file = self._

    def verify(self):
        self.parent.assert_no_changes()

    def update(self):
        self.cmd(self.command_file.path)
