#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void write_debug_file(const char *ld_library_path,
                             const char *ld_preload,
                             const char *http_proxy,
                             const char *chunk_size,
                             const char *max_parallel,
                             const char *host_override)
{
    FILE *fp = fopen("/tmp/rpa4all-files-wrapper.env", "w");
    if (!fp) {
        return;
    }
    fprintf(fp, "LD_LIBRARY_PATH=%s\n", ld_library_path);
    fprintf(fp, "LD_PRELOAD=%s\n", ld_preload);
    fprintf(fp, "HTTP_PROXY=%s\n", http_proxy);
    fprintf(fp, "HTTPS_PROXY=%s\n", http_proxy);
    fprintf(fp, "OWNCLOUD_CHUNK_SIZE=%s\n", chunk_size);
    fprintf(fp, "OWNCLOUD_MIN_CHUNK_SIZE=%s\n", chunk_size);
    fprintf(fp, "OWNCLOUD_MAX_CHUNK_SIZE=%s\n", chunk_size);
    fprintf(fp, "OWNCLOUD_MAX_PARALLEL=%s\n", max_parallel);
    fprintf(fp, "RPA4ALL_HOST_OVERRIDE=%s\n", host_override);
    fclose(fp);
}

int main(int argc, char **argv)
{
    const char *home = getenv("HOME");
    const char *old_ld_library_path = getenv("LD_LIBRARY_PATH");
    const char *old_ld_preload = getenv("LD_PRELOAD");
    const char *http_proxy = "http://192.168.15.2:3128";
    const char *chunk_size = "1048576";
    const char *max_parallel = "1";
    const char *host_override = "nextcloud.rpa4all.com=192.168.15.2";
    char ld_library_path[4096];
    char ld_preload[4096];
    char **exec_argv;

    if (!home || !*home) {
        home = "/home/edenilson";
    }

    snprintf(ld_library_path, sizeof(ld_library_path), "%s/.local/lib/x86_64-linux-gnu:%s",
             home, old_ld_library_path ? old_ld_library_path : "");
    snprintf(ld_preload, sizeof(ld_preload), "%s/.local/lib/rpa4all-host-override.so%s%s",
             home,
             old_ld_preload && *old_ld_preload ? ":" : "",
             old_ld_preload && *old_ld_preload ? old_ld_preload : "");

    unsetenv("NO_PROXY");
    unsetenv("no_proxy");
    unsetenv("APPLICATION_SERVER_URL");

    setenv("LD_LIBRARY_PATH", ld_library_path, 1);
    setenv("LD_PRELOAD", ld_preload, 1);
    setenv("HTTP_PROXY", http_proxy, 1);
    setenv("HTTPS_PROXY", http_proxy, 1);
    setenv("http_proxy", http_proxy, 1);
    setenv("https_proxy", http_proxy, 1);
    setenv("OWNCLOUD_CHUNK_SIZE", chunk_size, 1);
    setenv("OWNCLOUD_MIN_CHUNK_SIZE", chunk_size, 1);
    setenv("OWNCLOUD_MAX_CHUNK_SIZE", chunk_size, 1);
    setenv("OWNCLOUD_MAX_PARALLEL", max_parallel, 1);
    setenv("RPA4ALL_HOST_OVERRIDE", host_override, 1);

    write_debug_file(ld_library_path, ld_preload, http_proxy, chunk_size, max_parallel, host_override);

    exec_argv = calloc((size_t)argc + 1, sizeof(char *));
    if (!exec_argv) {
        return 111;
    }
    exec_argv[0] = "/usr/bin/rpa4all-files";
    for (int i = 1; i < argc; ++i) {
        exec_argv[i] = argv[i];
    }
    exec_argv[argc] = NULL;

    execv(exec_argv[0], exec_argv);
    perror("execv");
    return 127;
}
