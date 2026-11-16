/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Offline transmit frame assembler. It has no USB, modem or RF access. */
#include "p25.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
static int number(const char *s,unsigned base,unsigned long max,unsigned long *n){
 char *end;errno=0;*n=strtoul(s,&end,(int)base);
 return errno||*end||!*s||*s=='-'||*n>max?-1:0;
}
int main(int argc,char **argv){
 p25_call call={0};FILE *in,*out;uint8_t raw[144],frame[P25_LDU_BYTES],lsd[2]={0};
 uint16_t imbe[9][8];const char *input=NULL,*output=NULL;unsigned long n;int i,j,k,duid=P25_DUID_LDU1;size_t count,ldus=0;
 call.nac=0x293;call.talkgroup=9;call.source_id=1;
 for(i=1;i<argc;i++){
  if(i+1>=argc){fprintf(stderr,"Missing value\n");return 2;}
  if(!strcmp(argv[i],"--imbe")){input=argv[++i];continue;}
  if(!strcmp(argv[i],"--out")){output=argv[++i];continue;}
  if(!strcmp(argv[i],"--nac")){if(number(argv[++i],16,0xfff,&n))return 2;call.nac=(uint16_t)n;continue;}
  if(!strcmp(argv[i],"--tg")){if(number(argv[++i],10,65535,&n)||!n)return 2;call.talkgroup=(uint16_t)n;continue;}
  if(!strcmp(argv[i],"--id")){if(number(argv[++i],10,0xffffff,&n)||!n)return 2;call.source_id=(uint32_t)n;continue;}
  fprintf(stderr,"Unknown option %s\n",argv[i]);return 2;
 }
 if(!input||!output||!strcmp(input,output)){
  fprintf(stderr,"Usage: p25-txfile --imbe vectors.be16 --out call.bin [--nac 293 --tg 9 --id 1234567]\n");return 2;
 }
 in=fopen(input,"rb");if(!in){perror(input);return 1;}
 /* Validate complete nine-vector LDUs before creating the output. */
 if(fseek(in,0,SEEK_END)||ftell(in)<=0||ftell(in)%144||fseek(in,0,SEEK_SET)){
  fprintf(stderr,"Input must contain one or more complete 9x8 BE16 IMBE-vector groups (144 bytes each).\n");fclose(in);return 2;
 }
 out=fopen(output,"wb");if(!out){perror(output);fclose(in);return 1;}
 if(p25_encode_hdu(&call,frame)||fwrite(frame,1,P25_HDU_BYTES,out)!=P25_HDU_BYTES)goto fail;
 while((count=fread(raw,1,sizeof raw,in))==sizeof raw){
  for(j=0;j<9;j++)for(k=0;k<8;k++){
   unsigned off=(unsigned)(j*16+k*2);imbe[j][k]=(uint16_t)(((unsigned)raw[off]<<8)|raw[off+1]);
  }
  if(p25_encode_ldu(&call,(uint8_t)duid,(const uint16_t (*)[8])imbe,lsd,frame)||fwrite(frame,1,P25_LDU_BYTES,out)!=P25_LDU_BYTES)goto fail;
  duid=duid==P25_DUID_LDU1?P25_DUID_LDU2:P25_DUID_LDU1;ldus++;
 }
 if(count||ferror(in)||p25_encode_tdu(&call,frame)||fwrite(frame,1,P25_TDU_BYTES,out)!=P25_TDU_BYTES)goto fail;
 fclose(in);if(fclose(out)){perror(output);remove(output);return 1;}
 fprintf(stderr,"Wrote HDU + %lu alternating voice LDUs + TDU. Offline bits only; no radio transmission.\n",(unsigned long)ldus);return 0;
 fail:fprintf(stderr,"Frame assembly failed\n");fclose(in);fclose(out);remove(output);return 1;
}
