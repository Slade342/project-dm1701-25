/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stddef.h>

void *memset(void *dst, int value, size_t n)
{
    unsigned char *p = (unsigned char *)dst;
    while (n--) *p++ = (unsigned char)value;
    return dst;
}
void *memcpy(void *dst, const void *src, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (n--) *d++ = *s++;
    return dst;
}
void *memmove(void *dst, const void *src, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    if (d < s) while (n--) *d++ = *s++;
    else { d += n; s += n; while (n--) *--d = *--s; }
    return dst;
}
void __aeabi_memclr4(void *dst, size_t n)
{
    (void)memset(dst, 0, n);
}
int printf(const char *format, ...)
{
    (void)format;
    return 0;
}
void abort(void)
{
    for (;;) {}
}
