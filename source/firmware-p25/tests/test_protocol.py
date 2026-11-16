# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from Open25-DM32 tests/protocol/test_p25.py; see PROVENANCE.md.
#!/usr/bin/env python3
"""Compile portable CAI, compare pinned OP25, exercise FEC and stream loss.

Reference functions are loaded from the pristine source AST without executing
its CLI or import-time outfile creation. No RF hardware is touched.
"""
import ast
import contextlib
import ctypes as C
import hashlib
import io
import json
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "vendor/op25"
PIN = "3f44d43eb449bb4753247ce848bb42a403823dea"
SEED = 0x2532
rng = random.Random(SEED)


class Call(C.Structure):
    _fields_ = [("nac", C.c_uint16), ("talkgroup", C.c_uint16),
                ("source_id", C.c_uint32), ("manufacturer_id", C.c_uint8),
                ("service_options", C.c_uint8), ("status_symbol", C.c_uint8)]


class NID(C.Structure):
    _fields_ = [("nac", C.c_uint16), ("duid", C.c_uint8), ("corrected_bits", C.c_uint8)]


class Decoded(C.Structure):
    _fields_ = [("nid", NID), ("metadata_valid", C.c_uint8), ("clear_voice", C.c_uint8),
                ("manufacturer_id", C.c_uint8), ("service_options", C.c_uint8),
                ("link_control_format", C.c_uint8), ("algorithm_id", C.c_uint8),
                ("key_id", C.c_uint16), ("talkgroup", C.c_uint16), ("source_id", C.c_uint32),
                ("message_indicator", C.c_uint8 * 9), ("low_speed_data", C.c_uint8 * 2),
                ("low_speed_valid", C.c_uint8 * 2), ("metadata_corrected_bits", C.c_uint16),
                ("metadata_corrected_symbols", C.c_uint8), ("voice_corrected_bits", C.c_uint8 * 9),
                ("voice_u0_corrected_bits", C.c_uint8 * 9), ("imbe", (C.c_uint16 * 8) * 9)]


class RX(C.Structure):
    _fields_ = [("sync_shift", C.c_uint64), ("symbols_seen", C.c_uint32),
                ("sync_acquisitions", C.c_uint32), ("complete_frames", C.c_uint32),
                ("bad_nids", C.c_uint32), ("truncated_frames", C.c_uint32),
                ("expected_nac", C.c_uint16), ("symbols", C.c_uint16),
                ("target_symbols", C.c_uint16), ("max_sync_errors", C.c_uint8),
                ("inverted", C.c_uint8), ("frame", C.c_uint8 * 216), ("nid", NID)]


def packed(bits):
    return bytes(sum(bits[i + j] << (7-j) for j in range(8)) for i in range(0, len(bits), 8))


def bits(data):
    return [(b >> shift) & 1 for b in data for shift in range(7, -1, -1)]


def physical(logical):
    return logical + 2 * (logical // 70)


def configure(lib):
    lib.p25_nid_encode.argtypes = [C.c_uint16, C.c_uint8]
    lib.p25_nid_encode.restype = C.c_uint64
    lib.p25_nid_decode.argtypes = [C.c_uint64, C.POINTER(NID)]
    lib.p25_decode_frame.argtypes = [C.c_void_p, C.c_size_t, C.POINTER(Decoded)]
    lib.p25_rs_encode.argtypes = [C.c_void_p, C.c_size_t, C.c_uint, C.c_void_p]
    lib.p25_rs_decode.argtypes = [C.c_void_p, C.c_size_t, C.c_uint]
    lib.p25_imbe_encode.argtypes = [C.c_void_p, C.c_void_p]
    lib.p25_imbe_decode.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]
    lib.p25_rx_init.argtypes = [C.POINTER(RX), C.c_uint16, C.c_uint8]
    lib.p25_rx_push_dibit.argtypes = [C.POINTER(RX), C.c_uint8]




def make_reference(ref, function, *args):
    sink = io.BytesIO()
    ref["outfile"] = sink
    with contextlib.redirect_stdout(io.StringIO()):
        ref[function](*args)
    return sink.getvalue()


def encode(lib, function, call, n, *args):
    out = (C.c_uint8 * n)()
    assert getattr(lib, function)(C.byref(call), *args, out) == 0
    return bytes(out)


def assert_metadata(lib, frame, duid, nac, tgid, source=None):
    out = Decoded()
    assert lib.p25_decode_frame(frame, len(frame), C.byref(out)) == 0
    assert out.nid.duid == duid and out.nid.nac == nac
    assert out.metadata_valid and out.clear_voice
    assert out.talkgroup == tgid if duid != 10 else out.algorithm_id == 0x80
    if source is not None: assert out.source_id == source
    return out




def test_nid(lib, ref):
    total = 0
    for nac in range(4096):
        for duid in (0, 3, 5, 10, 15):
            code = ref["bch_64_16_23_encode"]((nac << 4) | duid)
            assert code == lib.p25_nid_encode(nac, duid)
            decoded = NID()
            assert lib.p25_nid_decode(code, C.byref(decoded)) == 0
            assert decoded.nac == nac and decoded.duid == duid and decoded.corrected_bits == 0
            total += 1
    for _ in range(1000):
        nac = rng.randrange(4096)
        duid = rng.choice((0, 3, 5, 10, 15))
        code = lib.p25_nid_encode(nac, duid)
        nerrors = rng.randrange(12)
        damaged = code ^ sum(1 << p for p in rng.sample(range(64), nerrors))
        decoded = NID()
        assert lib.p25_nid_decode(damaged, C.byref(decoded)) == 0
        assert (decoded.nac, decoded.duid, decoded.corrected_bits) == (nac, duid, nerrors)
    for duid in (1, 2, 4, 6, 7, 8, 9, 11, 12, 13, 14):
        assert lib.p25_nid_decode(lib.p25_nid_encode(0x293, duid), C.byref(NID())) < 0
    return {"all_nac_voice_duid_vectors": total, "random_0_to_11_error_vectors": 1000}








def test_frames(lib, ref):
    fixtures = []
    outdir = ROOT / "tests/protocol/vectors"
    outdir.mkdir(parents=True, exist_ok=True)
    for idx in range(50):
        nac, tg, src = (0x293, 123, 123456) if idx == 0 else (rng.randrange(4096), rng.randrange(65536), rng.randrange(1 << 24))
        ss = 0 if idx == 0 else rng.randrange(4)
        call = Call(nac, tg, src, 0, 0, ss)
        hdu = encode(lib, "p25_encode_hdu", call, 99)
        assert hdu == make_reference(ref, "construct_hdu", nac, ss, 0, 0, 0x80, 0, tg)
        assert_metadata(lib, hdu, 0, nac, tg)
        tdu = encode(lib, "p25_encode_tdu", call, 18)
        assert tdu == make_reference(ref, "construct_stdu", nac, ss)
        tdulc = encode(lib, "p25_encode_tdulc", call, 54)
        assert tdulc == make_reference(ref, "construct_xtdu", nac, ss, 0, 0, 0, 0, tg, 0, src)
        assert_metadata(lib, tdulc, 15, nac, tg, src)
        # P25craft repeats an already channel-interleaved IMBE144 word. Our
        # encoder accepts nine parameter vectors. Give every vector identical
        # data except the protocol-owned sync bit; compare full over-air bytes.
        u = [0x321, 0x456, 0x789, 0xabc, 0x123, 0x456, 0x789, 0x5a] if idx == 0 else [rng.randrange(1 << (12 if i < 4 else 11 if i < 7 else 7)) for i in range(8)]
        u[7] &= ~1
        frames = ((C.c_uint16 * 8) * 9)(*[(C.c_uint16 * 8)(*u) for _ in range(9)])
        cw = (C.c_uint8 * 18)()
        lib.p25_imbe_encode(frames[0], cw)
        # Convert sequential coded bits to the local 144-bit interleave.
        inner = [0] * 144
        for j, bit in enumerate(bits(cw)): inner[6 * (j % 24) + ((j // 24) ^ (j & 1))] = bit
        imbe = int.from_bytes(packed(inner), "big")
        lsd_value = 0x12345678 if idx == 0 else rng.randrange(1 << 32)
        ldus = []
        for duid in (5, 10):
            pair = (C.c_uint8 * 2)(*lsd_value.to_bytes(4, "big")[(0 if duid == 5 else 2):(2 if duid == 5 else 4)])
            ldu = encode(lib, "p25_encode_ldu", call, 216, duid, frames, pair)
            if duid == 5:
                expected = make_reference(ref, "construct_ldu1", nac, ss, imbe, lsd_value, 0, 0, 0, 0, tg, 0, src)
            else:
                expected = make_reference(ref, "construct_ldu2", nac, ss, imbe, lsd_value, 0, 0x80, 0)
            assert ldu == expected
            decoded = assert_metadata(lib, ldu, duid, nac, tg, src if duid == 5 else None)
            for i in range(9):
                assert list(decoded.imbe[i])[:7] == u[:7]
                assert decoded.imbe[i][7] == (u[7] | ((i + (duid == 10)) & 1))
            assert list(decoded.low_speed_data) == list(pair) and all(decoded.low_speed_valid)
            ldus.append(ldu)
        if idx == 0:
            for name, data in (("hdu", hdu), ("ldu1", ldus[0]), ("ldu2", ldus[1]), ("tdu", tdu), ("tdulc", tdulc)):
                path = outdir / f"nac293-{name}.bin"
                path.write_bytes(data)
                fixtures.append({"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            (outdir / "clear-call.bin").write_bytes(hdu + b"".join(ldus) + tdu)
    return {"full_frame_p25craft_vectors": 250, "fixtures": fixtures}


def test_stream(lib):
    path = ROOT / "tests/protocol/vectors/clear-call.bin"
    data = path.read_bytes()
    dibits = [(b >> s) & 3 for b in data for s in (6, 4, 2, 0)]
    for inverted in (False, True):
        rx = RX()
        lib.p25_rx_init(C.byref(rx), 0x293, 0)
        seen = []
        for d in [0] * 31 + dibits:
            if lib.p25_rx_push_dibit(C.byref(rx), d ^ (2 if inverted else 0)) == 1:
                seen.append((rx.nid.nac, rx.nid.duid, bytes(rx.frame[:lib.p25_frame_bytes(rx.nid.duid)])))
        assert [n[1] for n in seen] == [0, 5, 10, 3]
        assert rx.bad_nids == 0 and rx.truncated_frames == 0
        assert rx.complete_frames == 4
    rx = RX()
    lib.p25_rx_init(C.byref(rx), 0x123, 0)
    for d in dibits: assert lib.p25_rx_push_dibit(C.byref(rx), d) == 0
    assert rx.bad_nids == 4
    # Drop body bits, retain the next frame sync: truncated frames must never
    # be emitted as complete. Reacquire next complete LDU2 and terminator.
    rx = RX()
    lib.p25_rx_init(C.byref(rx), 0x293, 0)
    damaged = dibits[:396 + 200] + dibits[396 + 864:]
    seen = []
    for d in damaged:
        if lib.p25_rx_push_dibit(C.byref(rx), d) == 1: seen.append(rx.nid.duid)
    assert seen == [0, 10, 3] and rx.truncated_frames == 1
    # Two errors in frame sync are tolerated but wrong NAC is still rejected.
    rx = RX()
    lib.p25_rx_init(C.byref(rx), 0x293, 2)
    damaged = dibits[:]
    damaged[3] ^= 1; damaged[8] ^= 2
    seen = []
    for d in damaged:
        if lib.p25_rx_push_dibit(C.byref(rx), d) == 1: seen.append(rx.nid.duid)
    assert seen == [0, 5, 10, 3]
    assert lib.p25_rx_push_dibit(C.byref(rx), 4) == -1
    return {"stream_cases": ["normal", "inverted", "wrong_nac", "truncated_reacquisition", "two_sync_errors", "invalid_dibit"]}


def test_damage(lib, ref):
    path = ROOT / "tests/protocol/vectors"
    hdu = (path / "nac293-hdu.bin").read_bytes()
    ldu1 = (path / "nac293-ldu1.bin").read_bytes()
    for count in (1, 4, 8):
        raw = bits(hdu)
        # Four errors within one shortened Golay word exceed its t=3. The
        # outer RS layer must still repair the erroneous systematic symbol.
        for symbol in range(count):
            for bit in range(4): raw[physical(112 + 18 * symbol + bit)] ^= 1
        decoded = assert_metadata(lib, packed(raw), 0, 0x293, 123)
        assert decoded.metadata_corrected_symbols == count
    raw = bits(hdu)
    for symbol in range(9):
        for bit in range(4): raw[physical(112 + 18 * symbol + bit)] ^= 1
    decoded = Decoded()
    assert lib.p25_decode_frame(packed(raw), len(hdu), C.byref(decoded)) == 0
    assert not decoded.metadata_valid and not decoded.clear_voice
    for count in (1, 3, 6):
        raw = bits(ldu1)
        for symbol in range(count):
            start = 400 + 184 * (symbol // 4) + 10 * (symbol % 4)
            for bit in range(2): raw[physical(start + bit)] ^= 1
        decoded = assert_metadata(lib, packed(raw), 5, 0x293, 123, 123456)
        assert decoded.metadata_corrected_symbols == count
    # Ciphered metadata is identified for audio gating; no encryption code.
    encrypted = make_reference(ref, "construct_hdu", 0x293, 1, 0, 0, 0x84, 1, 123)
    assert lib.p25_decode_frame(encrypted, len(encrypted), C.byref(decoded)) == 0
    assert decoded.metadata_valid and not decoded.clear_voice
    assert decoded.algorithm_id == 0x84 and decoded.key_id == 1
    for size in (0, 1, 17, 18, 98, 100, 215, 216):
        assert lib.p25_decode_frame(hdu + bytes(217), size, C.byref(decoded)) < 0
    invalid_sync = bytes(6) + hdu[6:]
    assert lib.p25_decode_frame(invalid_sync, len(hdu), C.byref(decoded)) < 0
    # Standard MFID1 has the same standard-format LC definition as MFID0.
    standard_one = Call(0x293, 123, 123456, 1, 0, 0)
    tdulc = encode(lib, "p25_encode_tdulc", standard_one, 54)
    assert tdulc == make_reference(ref, "construct_xtdu", 0x293, 0, 0, 1, 0, 0, 123, 0, 123456)
    decoded = assert_metadata(lib, tdulc, 15, 0x293, 123, 123456)
    assert decoded.manufacturer_id == 1
    return {"damaged_metadata_cases": 7, "encrypted_audio_flag": "clear_voice_false", "invalid_lengths_and_sync": "rejected"}





def reference():
    path = UP / "p25craft.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "27079a321f75bda5db8d3ef6dd30d65992dbf8b6c73a2c608b43f3f745e9e2d9"
    tree = ast.parse(path.read_text())
    namespace = {"sys": __import__("sys"), "struct": __import__("struct"), "outfile": None, "quiet": True, "flip": 0}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), str(path), "exec"), namespace)
    namespace["text_out"] = lambda _: None
    return namespace


def main():
    subprocess.run([__import__("sys").executable, str(ROOT / "vendor/open25/generate_tables.py"), "--check"], check=True)
    ref = reference()
    results = {"reference_op25_commit": PIN, "random_seed": SEED, "hardware_verified": False}
    with tempfile.TemporaryDirectory(prefix="dm1701-p25-test-") as dirname:
        tmp = Path(dirname)
        output = tmp / "libp25.so"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-O2", "-shared", "-fPIC", str(ROOT / "vendor/open25/p25.c"), "-o", str(output)], check=True)
        lib = C.CDLL(str(output))
        configure(lib)
        for name, function, args in (("nid", test_nid, (lib, ref)), ("frames", test_frames, (lib, ref)), ("stream", test_stream, (lib,)), ("damage", test_damage, (lib, ref))):
            results[name] = function(*args)
            print(f"PASS {name}")
    results["status"] = "passed"
    report = ROOT / "build/protocol-results.json"
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(results, indent=2) + "\n")
    print(report)


if __name__ == "__main__": main()
