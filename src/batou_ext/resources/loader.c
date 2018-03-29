#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>


int main(int argc, char* argv[]) {
    int result;
    int i;
    char *loaded = getenv("pythonEnvLoaded");
    char *newargs[argc + 2];

    if (loaded) {
        // If the environment is already loaded, don't load again
        for (i=0; i<argc; i++){
           newargs[i] = argv[i];
         }
        newargs[argc] = 0;

        result = execvp("{{component.python}}",
                        newargs);
        fprintf(stderr, "Python loader (reentry) fail: %d / %d\n",
                result, errno);
        exit(errno);
    }

    newargs[0] = "{{component.env_file.path}}";
    for (i=0; i<argc; i++){
       newargs[i+1] = argv[i];
     }
    newargs[argc+2] = 0;

    result = execvp("{{component.env_file.path}}",
                    newargs);
    fprintf(stderr, "Python loader (initial) fail: %d / %d\n", result, errno);
    exit(errno);

}
