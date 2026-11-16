/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Newlib's assertion/abort path expects process hooks on bare metal. */
#include <errno.h>
int _getpid(void) {return 1;}
int _kill(int pid,int signal) {(void)pid;(void)signal;errno=ENOSYS;return -1;}
