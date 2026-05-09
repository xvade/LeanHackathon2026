/*
 * score_client.c — Lean FFI stub for the neural split ranker server.
 *
 * Connects to the inference server (scripts/server.py) over a Unix socket,
 * sends the pretty-printed goal and candidate expressions as text, and
 * receives a float64 score back.
 *
 * Protocol:
 *   Client → Server:  "<goal_pp>\n<cand_pp>\n\n"
 *   Server → Client:  8 bytes, little-endian double (the score)
 *
 * The server must be running before any neural_grind call:
 *   python3 scripts/server.py &
 */

#include <lean/lean.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>

#define SOCKET_PATH "/tmp/neural_grind.sock"

static double fallback_score(const char* goal, const char* cand) {
    /* If the server is not running, fall back to a length heuristic so
       proofs still work. Log a warning once. */
    static int warned = 0;
    if (!warned) {
        fprintf(stderr, "[neural_grind] WARNING: server not running at %s, "
                        "using length heuristic\n", SOCKET_PATH);
        warned = 1;
    }
    (void)goal;
    return -(double)strlen(cand);
}

LEAN_EXPORT double lean_neural_score(lean_object* goal_str, lean_object* cand_str) {
    const char* goal = lean_string_cstr(goal_str);
    const char* cand = lean_string_cstr(cand_str);

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return fallback_score(goal, cand);

    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(fd);
        return fallback_score(goal, cand);
    }

    /* Send: goal\ncand\n\n */
    dprintf(fd, "%s\n%s\n\n", goal, cand);

    /* Receive: 8 bytes little-endian double */
    double score = 0.0;
    ssize_t received = 0;
    while (received < (ssize_t)sizeof(double)) {
        ssize_t n = read(fd, (char*)&score + received, sizeof(double) - received);
        if (n <= 0) { close(fd); return fallback_score(goal, cand); }
        received += n;
    }

    close(fd);
    return score;
}
