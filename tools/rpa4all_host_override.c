#define _GNU_SOURCE

#include <dlfcn.h>
#include <netdb.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*getaddrinfo_fn)(const char *, const char *, const struct addrinfo *, struct addrinfo **);
typedef int (*connect_fn)(int, const struct sockaddr *, socklen_t);

static getaddrinfo_fn real_getaddrinfo(void)
{
    static getaddrinfo_fn fn = NULL;
    if (!fn) {
        fn = (getaddrinfo_fn)dlsym(RTLD_NEXT, "getaddrinfo");
    }
    return fn;
}

static connect_fn real_connect(void)
{
    static connect_fn fn = NULL;
    if (!fn) {
        fn = (connect_fn)dlsym(RTLD_NEXT, "connect");
    }
    return fn;
}

static int parse_override(const char *node, const char **target_host)
{
    const char *mapping = getenv("RPA4ALL_HOST_OVERRIDE");
    const char *fallback = "nextcloud.rpa4all.com=192.168.15.2";
    const char *source = (mapping && *mapping) ? mapping : fallback;
    const char *eq = strchr(source, '=');
    size_t name_len;

    if (!eq) {
        return 0;
    }

    name_len = (size_t)(eq - source);
    if (strncmp(node, source, name_len) != 0 || node[name_len] != '\0') {
        return 0;
    }

    *target_host = eq + 1;
    return **target_host != '\0';
}

static int parse_target_ipv4(struct in_addr *addr)
{
    const char *target_host = NULL;
    getaddrinfo_fn next = real_getaddrinfo();
    struct addrinfo hints;
    struct addrinfo *res = NULL;
    int rc;

    if (!parse_override("nextcloud.rpa4all.com", &target_host) || !next) {
        return 0;
    }

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    rc = next(target_host, "443", &hints, &res);
    if (rc != 0 || !res || res->ai_family != AF_INET) {
        if (res) {
            freeaddrinfo(res);
        }
        return 0;
    }

    *addr = ((struct sockaddr_in *)res->ai_addr)->sin_addr;
    freeaddrinfo(res);
    return 1;
}

static int is_public_https_target(const struct sockaddr_in *sin)
{
    unsigned ip = ntohl(sin->sin_addr.s_addr);
    unsigned a = (ip >> 24) & 0xff;
    unsigned b = (ip >> 16) & 0xff;

    if (ntohs(sin->sin_port) != 443) {
        return 0;
    }
    if (a == 10 || a == 127) {
        return 0;
    }
    if (a == 172 && b >= 16 && b <= 31) {
        return 0;
    }
    if (a == 192 && b == 168) {
        return 0;
    }
    if (a == 169 && b == 254) {
        return 0;
    }
    return 1;
}

int getaddrinfo(const char *node, const char *service, const struct addrinfo *hints, struct addrinfo **res)
{
    const char *target_host = NULL;
    struct addrinfo local_hints;
    struct addrinfo *tmp = NULL;
    int rc;
    getaddrinfo_fn next = real_getaddrinfo();

    if (!next) {
        return EAI_SYSTEM;
    }

    if (!node || !parse_override(node, &target_host)) {
        return next(node, service, hints, res);
    }

    memset(&local_hints, 0, sizeof(local_hints));
    if (hints) {
        local_hints = *hints;
    }
    if (local_hints.ai_family == AF_UNSPEC) {
        local_hints.ai_family = AF_INET;
    }

    rc = next(target_host, service, &local_hints, &tmp);
    if (rc != 0) {
        return rc;
    }

    for (struct addrinfo *cur = tmp; cur; cur = cur->ai_next) {
        free(cur->ai_canonname);
        cur->ai_canonname = strdup(node);
    }

    *res = tmp;
    return 0;
}

int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen)
{
    connect_fn next = real_connect();
    struct in_addr target_addr;
    struct sockaddr_in redirected;

    if (!next || !addr || addr->sa_family != AF_INET || addrlen < sizeof(struct sockaddr_in)) {
        return next ? next(sockfd, addr, addrlen) : -1;
    }

    if (!parse_target_ipv4(&target_addr) || !is_public_https_target((const struct sockaddr_in *)addr)) {
        return next(sockfd, addr, addrlen);
    }

    redirected = *(const struct sockaddr_in *)addr;
    redirected.sin_addr = target_addr;
    return next(sockfd, (const struct sockaddr *)&redirected, sizeof(redirected));
}
