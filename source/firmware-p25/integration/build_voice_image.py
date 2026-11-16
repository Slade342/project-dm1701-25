#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the Project DM1701-25 derivative with P25 decoder/audio linked.

Never changes the clean RadioFoundry checkout. MIT notices remain in the copied
sources; GPL P25 integration is deliberately combined only in this derivative.
"""
from pathlib import Path
import argparse, importlib.util, json, hashlib, os, shutil, struct, subprocess, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
P25=ROOT/'firmware-p25'
OUT=ROOT/'firmware-voice'
DEFAULT_SOURCE=Path('/workspace/work/research/firmware/radiofoundry')
DEFAULT_TREE=Path('/workspace/work/dm1701-voice-derivative')

def run(command,**kwargs):
    print(' '.join(map(str,command)),flush=True)
    return subprocess.run(list(map(str,command)),check=True,**kwargs)

def replace(tree,name,old,new):
    path=tree/name;text=path.read_text()
    if old not in text:raise RuntimeError(f'{name}: upstream hook not found')
    path.write_text(text.replace(old,new,1))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    ap.add_argument('--tree',type=Path,default=DEFAULT_TREE)
    ap.add_argument('--cross',default='/workspace/work/arm-toolchain/root/usr/bin/arm-none-eabi-')
    args=ap.parse_args()
    if not args.tree.exists():
        shutil.copytree(args.source,args.tree,ignore=shutil.ignore_patterns('.git','build','codecs','AGENTS.md','__pycache__'))
    tree=args.tree
    # Fresh upstream sources for deterministic, repeatable transformations.
    for name in ('Makefile','core/radio/radio_task.c','core/radio/radio_sm.c','core/radio/tx_limit.c','core/debuglink/debuglink.c',
                 'core/ui/ui_screens.c','core/ui/ui_app.c','core/ui/ui_menus.c','core/codeplug/codeplug.c',
                 'platform/stm32f4/FreeRTOSConfig.h','core/settings/settings.h','core/settings/settings.c'):
        shutil.copyfile(args.source/name,tree/name)
    dest=tree/'core/p25';dest.mkdir(exist_ok=True)
    for p in HERE.glob('studio_p25.*'):shutil.copyfile(p,dest/p.name)
    shutil.copyfile(HERE/'studio_syscalls.c',dest/'studio_syscalls.c')
    for name in ('p25.c','p25.h','p25_runtime.h','golay_table.inc'):
        shutil.copyfile(P25/'vendor/open25'/name,dest/name)
    replace(tree,'Makefile','APP_DIRS := $(CORE_DIRS) $(PLATFORM_DIRS) $(BOARD_DIRS)',
            'APP_DIRS := $(CORE_DIRS) $(PLATFORM_DIRS) $(BOARD_DIRS) core/p25\n')
    replace(tree,'Makefile','INCLUDES :=','INCLUDES := -Icore/p25 ')
    replace(tree,'Makefile','$(APP_OBJ) $(TP_OBJ): $(BUILD)/flags','$(APP_OBJ) $(TP_OBJ): $(BUILD)/flags\nOBJ += $(wildcard build/imbe/*.o)')
    replace(tree,'core/radio/radio_sm.c','#include "radio/radio_sm.h"','#include "radio/radio_sm.h"\n#include "p25/studio_p25.h"')
    replace(tree,'core/radio/radio_sm.c','\t\tboard.radio->audio(open && !bcast);','\t\tif (!studio_p25_active()) board.radio->audio(open && !bcast);')
    replace(tree,'core/radio/radio_task.c','#include "radio/radio.h"','#include "radio/radio.h"\n#include "p25/studio_p25.h"')
    replace(tree,'core/radio/radio_task.c','left > 0 ? (TickType_t)left : 0','left > 0 ? (TickType_t)(left > 1 && studio_p25_active() ? 1 : left) : 0')
    replace(tree,'core/radio/radio_task.c','radio_sm_request(&sm, &req, hal_millis());','studio_p25_leave();\n\t\t\t\t\tradio_sm_request(&sm, &req, hal_millis());')
    replace(tree,'core/radio/radio_task.c','\t\tpublish();','\t\tstudio_p25_poll(&sm.view);\n\t\tpublish();')
    replace(tree,'core/radio/tx_limit.c','#include "radio/tx_limit.h"','#include "radio/tx_limit.h"\n#include "p25/studio_p25.h"')
    replace(tree,'core/radio/tx_limit.c','\tif (block) {','\tif (block || studio_p25_active()) {')
    replace(tree,'core/debuglink/debuglink.c','#include "config.h"','#include "config.h"\n#include "p25/studio_p25.h"')
    replace(tree,'core/debuglink/debuglink.c','\tswitch (cmd) {','\tswitch (cmd) {\n\tcase 0x30: return studio_p25_command(req,len,out,cap);')
    replace(tree,'core/codeplug/codeplug.c','{ "Simplex 145.500", 145500000u, RADIO_BW_25K },','{ "P25 443.250", 443250000u, RADIO_BW_12K5 },\n\t{ "Simplex 145.500", 145500000u, RADIO_BW_25K },')
    replace(tree,'platform/stm32f4/FreeRTOSConfig.h','(28 * 1024)','(36 * 1024)')
    replace(tree,'core/settings/settings.h','} settings_t;',
            '\t/* Studio derivative: persisted experimental receive profile. */\n'
            '\tuint32_t studio_p25_hz;\n\tuint16_t studio_p25_nac;\n'
            '\tuint8_t studio_p25_enable, studio_p25_mapping;\n} settings_t;')
    replace(tree,'core/settings/settings.c','sizeof(settings_t) == 396','sizeof(settings_t) == 404')
    # Brand the derivative without removing upstream copyright/license lines.
    p=tree/'core/ui/ui_menus.c'
    p.write_text(p.read_text().replace('"RadioFoundry\\n"','"DM1701 Studio 0.3\\n"'))
    p=tree/'core/ui/ui_screens.c'
    p.write_text(p.read_text().replace('const char *word = "RadioFoundry";','const char *word = "DM1701 Studio";'))
    spec=importlib.util.spec_from_file_location('studio_radio_ui',P25/'radio-ui/apply_radio_ui.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.apply(tree)
    cc=args.cross+'gcc';cxx=args.cross+'g++'
    codec=P25/'voice';objdir=tree/'build/imbe';objdir.mkdir(parents=True,exist_ok=True)
    sources=['aux_sub.cc','basicop2.cc','ch_decode.cc','ch_encode.cc','decode.cc','dc_rmv.cc','dsp_sub.cc',
             'encode.cc','imbe_vocoder_impl.cc','math_sub.cc','pe_lpf.cc','pitch_est.cc','pitch_ref.cc',
             'qnt_sub.cc','rand_gen.cc','sa_decode.cc','sa_encode.cc','sa_enh.cc','tbls.cc','uv_synt.cc','v_synt.cc','v_uv_det.cc']
    flags=['-mcpu=cortex-m4','-mthumb','-mfpu=fpv4-sp-d16','-mfloat-abi=hard','-Os','-ffunction-sections',
           '-fdata-sections','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
           '-std=c++14','-fwrapv','-nostdinc++','-I'+str(codec/'arm_compat'),'-I'+str(codec/'vendor')]
    for source in [codec/'vendor'/x for x in sources]+[codec/'arm/p25_imbe_arm.cc']:
        run([cxx,*flags,'-c',source,'-o',objdir/(source.stem+'.o')])
    command=['make','-j8','BOARD=dm1701','BUILD=build/voice','CROSS='+args.cross,'LTO=1',
             'CONFIG_AUDIO_PROBE=y','CONFIG_USB_NETWORK=n','CONFIG_DMR_IP_GATEWAY=n',
             'CONFIG_HOTSPOT=n','CONFIG_SFR=n','CONFIG_APRS=n','CONFIG_GPS=n','CONFIG_BATTERY_SAVE=n',
             'CONFIG_VOX=n','CONFIG_DMR_SMS=n','CONFIG_DMR_ARS=n','CONFIG_DMR_LRRP=n',
             'CONFIG_DMR_SIGNALING=n','CONFIG_DMR_EMERGENCY=n','CONFIG_ZONE_SHARE=n','CONFIG_DMR_PRIVACY=n',
             'CONFIG_DMR_ROAMING=n','CONFIG_LANG_ES=n','CONFIG_IDDB_COMPACT=n','CONFIG_STUB_ENTRY=n']
    # Debian's extracted toolchain stores newlib separately from gcc's
    # relative search prefix. Keep this build usable without system installs.
    toolroot=Path(shutil.which(cc) or cc).resolve().parents[1]
    newlib=toolroot/'lib/arm-none-eabi/newlib'
    env=dict(os.environ)
    headers=toolroot/'include/newlib'
    if headers.is_dir():env['C_INCLUDE_PATH']=str(headers)
    if newlib.is_dir():
        hard=newlib/'thumb/v7e-m+fp/hard'
        command.append('LDSPECS=-B'+str(hard)+' --specs='+str(newlib/'nano.specs')+
                       ' --specs='+str(newlib/'nosys.specs')+' -L'+str(hard)+' -Wl,--no-warn-rwx-segments')
    run(command,cwd=tree,env=env)
    OUT.mkdir(exist_ok=True)
    base=tree/'build/voice/rfoundry_dm1701'
    image_prefix='PROJECT-DM1701-25-P25-EXPERIMENTAL'
    for suffix in ('.bin','.elf','.map'):
        shutil.copyfile(str(base)+suffix,OUT/(image_prefix+suffix))
        # A legacy alias avoids stranding an older Studio installation; new
        # Project DM1701-25 packages exclude this alias.
        shutil.copyfile(str(base)+suffix,OUT/('DM1701-P25-VOICE-EXPERIMENTAL'+suffix))
    data=(OUT/(image_prefix+'.bin')).read_bytes()
    sp,reset=struct.unpack_from('<II',data)
    if sp!=0x2001fffc or not 0x0800c001<=reset<0x080c0000 or not reset&1 or len(data)>737280:
        raise RuntimeError('Image vector/flash bounds validation failed')
    symbols=subprocess.check_output([args.cross+'nm','-S',str(base)+'.elf'],text=True)
    required=['studio_p25_poll','studio_p25_command','dm1701_imbe_decode_arm']
    missing=[x for x in required if x not in symbols]
    if missing:raise RuntimeError('Required linked symbols missing: '+str(missing))
    report={'build':'project-dm1701-25-p25-experimental-0.4','base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip(),
            'image_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'stack_pointer':hex(sp),'reset_vector':hex(reset),
            'flashable_application':True,'hardware_tested':False,'p25_rf_rx_verified':False,'p25_rf_tx':False,
            'linked_components':['C6000 continuous raw RX poll','8-order P25 framing/FEC acquisition','fixed-point IMBE decoder','16x160 PCM queue','board I2S speaker','radio home renderer'],
            'limits':['Conventional Phase1 C4FM RX only','C6000 raw36 RF path unmeasured','No trunk following, Phase2, encryption, or P25 transmit'],
            'build_command':list(map(str,command))}
    (OUT/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    for name in ('LICENSE','AUTHORS','CONTRIBUTORS'):
        if (args.source/name).exists():shutil.copyfile(args.source/name,OUT/('RadioFoundry-'+name))
    sys.path.insert(0,str(ROOT/'firmware-lab/vendor'))
    from rfoundry import boards, manifest
    meta=manifest.generate(boards.get('dm1701'),data,'project-dm1701-25-0.4-experimental',report['base_commit'],
            features='FM,DMR,P25_EXPERIMENTAL_RX,PROJECT_DM1701_25_HOME,NO_FILTER_SCAN',
                           toolchain=subprocess.check_output([cc,'-dumpfullversion'],text=True).strip(),
                           file_name=image_prefix+'.bin')
    meta['studio']={'hardware_tested':False,'p25_rf_rx_verified':False,'p25_rf_tx':False}
    manifest.verify(meta,data,'dm1701')
    (OUT/(image_prefix+'.json')).write_text(manifest.dumps(meta))
    # Keep the old manifest as a compatibility alias for Studio 0.3 copies.
    (OUT/'DM1701-P25-VOICE-EXPERIMENTAL.json').write_text(manifest.dumps(meta))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
