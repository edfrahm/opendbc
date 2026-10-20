#!/usr/bin/env python3
import os

chrysler_to_ram = {
  "_stellantis_common_ram_dt_generated.dbc": {
    258: 35,
    264: 37,
    268: 113,
    280: 181,
    284: 121,
    288: 123,
    320: 131,
    344: 139,
    368: 147,
    464: 464,
    500: 153,
    501: 232,
    544: 49,
    571: 177,
    559: 157,
    625: 163,
    669: 213,
    678: 250,
    720: 720,
    792: 792,
    820: 657,
  },
  "_stellantis_common_ram_hd_generated.dbc": {
    571: 570,
    678: 629,
  },
}

# Signals whose shared definition is wrong for one output: (source address, shared signal name) -> replacement line.
# Ram HD, verified on a 2022 Ram 2500's recorded drives (edfrahm/SP-RamHD-TICI-Port#5): the windshield unit's own
# measurement of the car its cruise control follows. Byte 7 of DAS_4 is that car's distance in meters (254 = no car),
# not a speed; byte 3 of DAS_5 is that car's speed, capped at the set speed, not the set speed.
signal_overrides = {
  "_stellantis_common_ram_hd_generated.dbc": {
    (501, "SPEED_DIGITAL"): ' SG_ LEAD_DISTANCE : 63|8@0+ (1,0) [0|254] "m" XXX\n',
    (625, "SET_SPEED_KPH"): ' SG_ LEAD_SPEED_KPH : 24|8@1+ (1,0) [0|250] "km/h" XXX\n',
  },
}


def generate():
  src = '_stellantis_common.dbc'
  chrysler_path = os.path.dirname(os.path.realpath(__file__))
  result = {}

  for out, addr_lookup in chrysler_to_ram.items():
    with open(os.path.join(chrysler_path, src), encoding='utf-8') as in_f:
      parts = [f'CM_ "Generated from {src}"\n\n']

      overrides = signal_overrides.get(out, {})
      wrote_addrs, used_overrides, msg_addr = set(), set(), None
      for line in in_f.readlines():
        if line.startswith(('BO_', 'VAL_')):
          sl = line.split(' ')
          addr = int(sl[1])
          wrote_addrs.add(addr)
          if line.startswith('BO_'):
            msg_addr = addr
          sl[1] = str(addr_lookup.get(addr, addr))
          line = ' '.join(sl)
        elif line.startswith(' SG_ ') and (msg_addr, line.split()[1]) in overrides:
          used_overrides.add((msg_addr, line.split()[1]))
          line = overrides[(msg_addr, line.split()[1])]
        parts.append(line)

      unused = set(overrides) - used_overrides
      assert len(unused) == 0, f"Signal overrides not found in {src}: {unused}"

      missing_addrs = set(addr_lookup.keys()) - wrote_addrs
      assert len(missing_addrs) == 0, f"Missing addrs from {src}: {missing_addrs}"

    result[out] = ''.join(parts)

  return result
