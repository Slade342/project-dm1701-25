/* SPDX-License-Identifier: GPL-3.0-or-later
 * Host capture decoder, DM-1701 P25 port work. No USB, RF, or flash access. */
#include "p25.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(FILE *out)
{
    fputs("Usage: p25-capture [--packed|--dibits] [--nac HEX|any] [--sync-errors 0..4] FILE\n"
          "FILE is already-demodulated P25 Phase 1 C4FM air bits, not WAV/IQ or\n"
          "an unverified C6000 RAM dump. --packed: MSB-first bits (default).\n"
          "--dibits: one binary byte per dibit, values 0..3. Use - for stdin.\n"
          "Emits frame metadata as JSON lines. No speech synthesis or RF operation.\n", out);
}
static int parse_number(const char *s, unsigned base, unsigned maximum, unsigned *out)
{
    char *end;
    errno=0;
    unsigned long n=strtoul(s,&end,(int)base);
    if (!*s || *end || errno || n>maximum) return 0;
    *out=(unsigned)n;return 1;
}
int main(int argc, char **argv)
{
    const char *path=NULL;
    unsigned nac=P25_NAC_ANY, errors=2;
    int packed=1;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--help")) { usage(stdout);return 0; }
        if (!strcmp(argv[i],"--packed")) { packed=1;continue; }
        if (!strcmp(argv[i],"--dibits")) { packed=0;continue; }
        if (!strcmp(argv[i],"--nac") && i+1<argc) {
            const char *value=argv[++i];
            if (!strcmp(value,"any")) nac=P25_NAC_ANY;
            else if (!parse_number(value,16,0xfff,&nac)) { fputs("invalid NAC\n",stderr);return 2; }
            continue;
        }
        if (!strcmp(argv[i],"--sync-errors") && i+1<argc) {
            if (!parse_number(argv[++i],10,4,&errors)) { fputs("invalid sync tolerance\n",stderr);return 2; }
            continue;
        }
        if (path || (argv[i][0]=='-' && strcmp(argv[i],"-"))) { usage(stderr);return 2; }
        path=argv[i];
    }
    if (!path) { usage(stderr);return 2; }
    FILE *in=!strcmp(path,"-")?stdin:fopen(path,"rb");
    if (!in) { perror(path);return 2; }
    p25_rx rx;
    p25_rx_init(&rx,(uint16_t)nac,(uint8_t)errors);
    unsigned decoded=0,failed=0;
    int byte;
    while ((byte=fgetc(in))!=EOF) {
        if (!packed && byte>3) { fputs("invalid dibit byte: require binary bytes 0..3\n",stderr);if(in!=stdin)fclose(in);return 2; }
        for (unsigned j=0;j<(packed?4u:1u);j++) {
            uint8_t dibit=packed?(uint8_t)((byte>>(6-2*j))&3):(uint8_t)byte;
            if (p25_rx_push_dibit(&rx,dibit)!=1) continue;
            p25_decoded frame;
            if (p25_decode_frame(rx.frame,p25_frame_bytes(rx.nid.duid),&frame)) { failed++;continue; }
            decoded++;
            printf("{\"frame\":%u,\"nac\":\"%03X\",\"duid\":%u,\"nid_corrected_bits\":%u,\"metadata_valid\":%s,\"clear_voice\":%s",
                   decoded,frame.nid.nac,frame.nid.duid,frame.nid.corrected_bits,
                   frame.metadata_valid?"true":"false",frame.metadata_valid&&frame.clear_voice?"true":"false");
            if(frame.metadata_valid) {
                if(frame.nid.duid==P25_DUID_HDU || frame.nid.duid==P25_DUID_LDU1 || frame.nid.duid==P25_DUID_TDULC)
                    printf(",\"talkgroup\":%u",frame.talkgroup);
                if(frame.nid.duid==P25_DUID_LDU1 || frame.nid.duid==P25_DUID_TDULC)
                    printf(",\"source_id\":%u",frame.source_id);
                if(frame.nid.duid==P25_DUID_HDU || frame.nid.duid==P25_DUID_LDU2)
                    printf(",\"algorithm_id\":%u,\"key_id\":%u",frame.algorithm_id,frame.key_id);
            }
            printf(",\"imbe_channel_frames\":%u}\n",frame.nid.duid==P25_DUID_LDU1||frame.nid.duid==P25_DUID_LDU2?9:0);
        }
    }
    int io_error=ferror(in);
    if(in!=stdin)fclose(in);
    fprintf(stderr,"{\"decoded_frames\":%u,\"decode_failures\":%u,\"bad_nids\":%u,\"truncated_frames\":%u,\"radio_qualified\":false}\n",
            decoded,failed,rx.bad_nids,rx.truncated_frames);
    if(io_error) { fputs("input read failed\n",stderr);return 2; }
    return decoded&&!failed?0:1;
}
