#!/usr/bin/env python

import struct
import io
from rich import print
import itertools as it
import more_itertools as mit
import dataclasses
from typing import List

def null_terminated_string(b: bytes) -> str:
    return bytes(it.takewhile(lambda e: e, b)).decode("UTF-8")


@dataclasses.dataclass
class PdbAttrs:
    deleted: bool
    archived: bool
    busy: bool
    secret: bool


@dataclasses.dataclass
class PdbHeader:
    name: str
    attrs: PdbAttrs
    version: int
    creation_time: int
    modification_time: int
    backup_time: int
    modification_number: int
    app_info: int
    sort_info: int
    pdb_type: str
    creator: str
    unique_id_seed: int
    next_record_list: int
    num_records: int


@dataclasses.dataclass
class PdbRecordHeader:
    number: int
    end: int
    offset: int
    attributes: PdbAttrs
    unique_id: int


def pdb_attrs_from_int(n: int) -> PdbAttrs:
    return PdbAttrs(
        deleted=bool(n & (0x01 << 3)),
        archived=bool(n & (0x01 << 2)),
        busy=bool(n & (0x01 << 1)),
        secret=bool(n & (0x01 << 0)),
    )


def pdb_header_from_bytes(b: bytes) -> PdbHeader:
    fields = list(struct.unpack(">32s 2H 6L 4s 4s 2L H", b[:78]))
    fields[0] = null_terminated_string(fields[0])
    fields[1] = pdb_attrs_from_int(fields[1])
    fields[9] = fields[9].decode("UTF-8")
    fields[10] = fields[10].decode("UTF-8")
    return PdbHeader(*fields)


def pdb_record_from_bytes(b: bytes, number: int) -> PdbRecordHeader:
    fields = list(struct.unpack("> L B 3s", b))
    fields[1] = pdb_attrs_from_int(fields[1])
    fields[2] = int.from_bytes(fields[2], "big")
    return PdbRecordHeader(number, 0, *fields)


@dataclasses.dataclass
class ItProjectFlags:
    is_stereo: bool
    vol_0_optimization: bool
    use_instruments: bool
    linear_slides: bool
    old_effects: bool
    link_effect_g: bool
    use_midi_pitch: bool
    request_embedded_midi: bool


@dataclasses.dataclass
class ItProjectSpecial:
    has_message: bool
    has_embedded_midi: bool


@dataclasses.dataclass
class ItProjectHeader:
    impm: str
    song_name: str
    pattern_hilight: int
    order_number: int
    instrument_number: int
    sample_number: int
    pattern_number: int
    created_with: str
    compatible_with: str
    flags: ItProjectFlags
    special: ItProjectSpecial
    global_volume: int
    mix_volume: int
    initial_speed: int
    initial_tempo: int
    panning_separation: int
    pitch_wheel_depth: int
    message_length: int
    message_offset: int
    channel_volumes: List[int]
    channel_pans: List[int]
    orders: List[int]
    instrument_offsets: List[int]
    sample_offsets: List[int]
    pattern_offsets: List[int]


@dataclasses.dataclass
class ItSampleHeader:
    imps: str
    dos_filename: str
    global_volume: int
    flag: int
    volume: int
    sample_name: str
    convert: int
    default_pan: int
    number_of_samples: int
    loop_begin: int
    loop_end: int
    c5_speed: int
    sustain_loop_start: int
    sustain_loop_end: int
    sample_pointer: int
    vibrato_speed: int
    vibrato_depth: int
    vibrato_rate: int
    vibrato_waveform_type: int


def it_project_flags_from_int(n: int) -> ItProjectFlags:
    return ItProjectFlags(
        is_stereo=bool(n & (0x01 << 0)),
        vol_0_optimization=bool(n & (0x01 << 1)),
        use_instruments=bool(n & (0x01 << 2)),
        linear_slides=bool(n & (0x01 << 3)),
        old_effects=bool(n & (0x01 << 4)),
        link_effect_g=bool(n & (0x01 << 5)),
        use_midi_pitch=bool(n & (0x01 << 6)),
        request_embedded_midi=bool(n & (0x01 << 7)),
    )


def it_project_special_from_int(n: int) -> ItProjectSpecial:
    return ItProjectSpecial(
        has_message=bool(n & (0x01 << 0)),
        has_embedded_midi=bool(n & (0x01 << 3)),
    )


def bytes_to_it_project_header(b: bytes) -> ItProjectHeader:
    fields = list(struct.unpack("< 4s 26s 9H 6B H L 4x 64s 64s", b[:0x00C0]))
    fields[7] = "{0:04x}".format(fields[7])
    fields[8] = "{0:04x}".format(fields[8])
    fields[9] = it_project_flags_from_int(fields[9])
    fields[10] = it_project_flags_from_int(fields[10])
    proj = ItProjectHeader(
        *fields,
        orders=[],
        instrument_offsets=[],
        sample_offsets=[],
        pattern_offsets=[],
    )
    variable_fields = struct.unpack(
        "< {}s {}s {}s {}s".format(
            proj.order_number,
            4 * proj.instrument_number,
            4 * proj.sample_number,
            4 * proj.pattern_number,
        ),
        b[0x00C0:],
    )

    proj.orders = list(variable_fields[0])
    proj.instrument_offsets = list(
        struct.unpack("<{}L".format(proj.instrument_number), variable_fields[1])
    )
    proj.sample_offsets = list(
        struct.unpack("<{}L".format(proj.sample_number), variable_fields[2])
    )
    proj.pattern_offsets = list(
        struct.unpack("<{}L".format(proj.pattern_number), variable_fields[3])
    )

    return proj


def bytes_to_it_sample_header(b: bytes) -> ItSampleHeader:
    fields = list(struct.unpack("< 4s 12s x 3B 26s 2B 7L 4B", b[:0x50]))
    fields[1] = null_terminated_string(fields[1])
    fields[5] = null_terminated_string(fields[5])
    # TODO: actually parse fields[4] and fields[7] into flags
    return ItSampleHeader(*fields)



with open("Mazera-music.pdb", "rb") as f:
    pdb_data = f.read()

pdb_header = pdb_header_from_bytes(pdb_data)
pdb_record_headers = []
for record_num in range(pdb_header.num_records):
    offset = 0x4E + (8 * record_num)
    pdb_record_headers.append(
        pdb_record_from_bytes(pdb_data[offset : offset + 0x08], record_num)
    )

# Sort by offset so we can take windows to get lengths
pdb_record_headers.sort(key=lambda rh: rh.offset)
for [rh, rh_next] in mit.windowed(it.chain(pdb_record_headers, [None]), 2):
    assert rh is not None
    if rh_next:
        rh.end = rh_next.offset
    else:
        rh.end = len(pdb_data) + 1

project_data = io.BytesIO()

def get_record_data(idx) -> bytes:
    rh = pdb_record_headers[idx]
    return pdb_data[rh.offset : rh.end]

it_project_header_bytes = get_record_data(0)

it_project_header = bytes_to_it_project_header(get_record_data(0))

project_data.write(it_project_header_bytes)
project_data.seek(it_project_header.pattern_offsets[0])
project_data.write(get_record_data(1))
project_data.write(get_record_data(2))
project_data.write(get_record_data(3))

# for pattern_offset in it_project_header.pattern_offsets:
#     fields = struct.unpack("< 2H", project_data.getbuffer()[pattern_offset : pattern_offset + 4])
#     pattern_len = fields[0]
#     print("pattern offset and end:", pattern_offset, pattern_offset + pattern_len + 8)

for sample_idx, sample_offset in enumerate(it_project_header.sample_offsets):
    pdb_rec_data = get_record_data(sample_idx + 4)
    sample_header = bytes_to_it_sample_header(pdb_rec_data)
    # print("sample offset:", sample_offset)
    # print("sample data offset:", sample_header.sample_pointer)
    project_data.seek(sample_offset)
    project_data.write(pdb_rec_data[:0x50])
    project_data.seek(sample_header.sample_pointer)
    project_data.write(pdb_rec_data[0x50:])

with open("mazera.it", "wb") as f:
    f.write(project_data.getbuffer())
