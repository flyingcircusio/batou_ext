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

    You can also provide ready-to-use-script by yourself:

    self += batou.lib.file.File('myscript', mode=0o744)
    self += batou_ext.run.Run('myscript', file=self._)

    The script is called only, if there are any changes at the parent
    component.
    """
    namevar = 'command'
    content = None
    file = None

    def configure(self):

        if not self.file and self.content:
            self += batou.lib.file.File(
                self.command, content=self.content, mode=0o700)
            self.command_file = self._
        elif self.file:
            self.command_file = self.file
        else:
            raise ValueError("You need to provide either content or file.")

    def verify(self):
        self.parent.assert_no_changes()

    def update(self):
        self.cmd(self.command_file.path)
