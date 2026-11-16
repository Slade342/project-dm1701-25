/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "imbe_vocoder_api.h"
extern "C" {
#include "p25.h"
}
#include <cstdio>
#include <cstring>
#include <memory>
#include <cstdint>
static bool emit_pcm(FILE *out,const int16_t *pcm){
 uint8_t raw[320];for(unsigned i=0;i<160;i++){raw[2*i]=(uint8_t)pcm[i];raw[2*i+1]=(uint8_t)((uint16_t)pcm[i]>>8);}
 return fwrite(raw,1,sizeof raw,out)==sizeof raw;
}
int main(int argc,char **argv){
 if(argc!=4||(strcmp(argv[1],"encode")&&strcmp(argv[1],"decode")&&strcmp(argv[1],"receive"))||!strcmp(argv[2],argv[3])){
  fprintf(stderr,"Usage: p25-voice encode|decode|receive INPUT OUTPUT\nPCM is mono 8000Hz signed16 little-endian; vectors are eight BE16 words per20ms. receive accepts packed on-air P25 bits.\n");return 2;
 }
 FILE *in=fopen(argv[2],"rb");if(!in){perror(argv[2]);return 1;}
 FILE *out=fopen(argv[3],"wb");if(!out){fclose(in);perror(argv[3]);return 1;}
 auto codec=std::make_unique<imbe_vocoder>();int16_t pcm[160]={0},u[8]={0};unsigned frames=0;bool ok=true;
 if(!strcmp(argv[1],"receive")){
  p25_rx rx;p25_rx_init(&rx,P25_NAC_ANY,2);int ch;bool clear=false;
  while((ch=fgetc(in))!=EOF){for(int shift=6;shift>=0;shift-=2){
   if(!p25_rx_push_dibit(&rx,(uint8_t)((ch>>shift)&3)))continue;
   p25_decoded d;if(p25_decode_frame(rx.frame,p25_frame_bytes(rx.nid.duid),&d)){clear=false;continue;}
   if(d.nid.duid==P25_DUID_TDU||d.nid.duid==P25_DUID_TDULC){clear=false;continue;}
   if(d.nid.duid==P25_DUID_HDU){codec=std::make_unique<imbe_vocoder>();clear=d.metadata_valid&&d.clear_voice;continue;}
   clear=d.metadata_valid&&d.clear_voice;
   if(d.nid.duid!=P25_DUID_LDU1&&d.nid.duid!=P25_DUID_LDU2)continue;
   for(unsigned j=0;j<9;j++){
    if(clear&&d.voice_corrected_bits[j]<=9){for(unsigned k=0;k<8;k++)u[k]=(int16_t)d.imbe[j][k];codec->imbe_decode(u,pcm);}
    else memset(pcm,0,sizeof pcm);
    if(!emit_pcm(out,pcm)){ok=false;break;}frames++;
   }
  }if(!ok)break;}
 }else{
  bool encoding=!strcmp(argv[1],"encode");uint8_t raw[320];size_t n,want=encoding?320u:16u;
  while((n=fread(raw,1,want,in))==want){
   if(encoding){
    for(unsigned j=0;j<160;j++)pcm[j]=(int16_t)((uint16_t)raw[2*j]|((uint16_t)raw[2*j+1]<<8));
    codec->imbe_encode(u,pcm);
    for(unsigned j=0;j<8;j++){raw[2*j]=(uint8_t)((uint16_t)u[j]>>8);raw[2*j+1]=(uint8_t)u[j];}
    if(fwrite(raw,1,16,out)!=16){ok=false;break;}
   }else{
    for(unsigned j=0;j<8;j++)u[j]=(int16_t)(((uint16_t)raw[2*j]<<8)|raw[2*j+1]);
    codec->imbe_decode(u,pcm);if(!emit_pcm(out,pcm)){ok=false;break;}
   }frames++;
  }
  if(n&&n!=want){fprintf(stderr,"Incomplete audio/vector frame\n");ok=false;}
 }
 if(ferror(in))ok=false;fclose(in);if(fclose(out))ok=false;
 if(!ok||!frames){remove(argv[3]);return 1;}
 fprintf(stderr,"Processed %u20ms frames; host codec only, no RF operation.\n",frames);return 0;
}
