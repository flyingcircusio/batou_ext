#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>


#define ARRAY_CONCAT(TYPE, A, An, B, Bn) \
(TYPE *)array_concat((const void *)(A), (An), (const void *)(B), (Bn), sizeof(TYPE));

void *array_concat(const void *a, size_t an,const void *b, size_t bn, size_t s)
{
    char *p = malloc((s+1) * (an + bn));
    memcpy(p, a, an*s);
    memcpy(p + an*s, b, bn*s);
    p[an+bn+1] = 0;
    return p;
}


int main(int argc, char* argv[]) {
    int result;
    char *loaded = getenv("pythonEnvLoaded");
    if (loaded) {
        // If the environment is already loaded, don't load again
        result = execvp("{{component.python}}}", argv);
        printf("Python loader fail: %d / %d", result, errno);
        exit(errno);
    }

    char *a[] = { "{{component.workdir}}setupEnv" };
    char **newargs = ARRAY_CONCAT(char*, a, 1, argv, argc);

    result = execvp("{{component.workdir}}/setupEnv-{{component.python}}",
                    newargs);

    printf("Python loader fail: %d / %d", result, errno);
    exit(errno);

}
