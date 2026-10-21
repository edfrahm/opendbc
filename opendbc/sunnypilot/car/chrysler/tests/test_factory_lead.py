"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import unittest

from opendbc.can import CANPacker
from opendbc.car import Bus
from opendbc.car.car_helpers import interfaces
from opendbc.car.chrysler.values import CAR, DBC
from opendbc.car.common.conversions import Conversions as CV

# Real frames from the windshield unit (bus 2), 2026-10-19 route 00000783 at 14:48:59.0: the factory cruise control
# engaged at 75 mph, following traffic that was stopping 88 m ahead at 23 km/h (edfrahm/SP-RamHD-TICI-Port#28).
DAS_4_AT_88M = bytes.fromhex("00794b20400d0058")  # byte 7: 88 m
DAS_4_NO_CAR = bytes.fromhex("00794b20400d00fe")  # byte 7: 254, no car
DAS_5_AT_23KPH = bytes.fromhex("1c000017000000ff")  # byte 3: 23 km/h; byte 7 is 0xFF and the counter 0 in every frame
DAS_5_SECOND = bytes.fromhex("1c000016000000ff")  # the next frame: same counter, 22 km/h


class TestFactoryLead(unittest.TestCase):
  def _interface(self, car_name):
    CarInterface = interfaces[car_name]
    CP = CarInterface.get_non_essential_params(car_name)
    CP_SP = CarInterface.get_non_essential_params_sp(CP, car_name)
    return CarInterface(CP, CP_SP)

  def _update(self, CI, frames, t):
    return CI.update([(t, frames)])

  def _das_3(self, packer, engaged, counter):
    return packer.make_can_msg("DAS_3", 2, {"ACC_AVAILABLE": 1, "ACC_ACTIVE": int(engaged), "COUNTER": counter % 16})

  def test_ram_hd_reads_the_units_car_while_engaged(self):
    CI = self._interface(CAR.RAM_HD_5TH_GEN)
    packer = CANPacker(DBC[CAR.RAM_HD_5TH_GEN][Bus.pt])
    t = 0
    for i, das_5 in enumerate([DAS_5_AT_23KPH, DAS_5_SECOND] * 5):
      t += 20_000_000
      frames = [self._das_3(packer, True, i), (0x1F5, DAS_4_AT_88M, 2), (0x271, das_5, 2)]
      _, CS_SP = self._update(CI, frames, t)
    self.assertTrue(CS_SP.factoryLead.present)
    self.assertEqual(CS_SP.factoryLead.dRel, 88.)
    self.assertAlmostEqual(CS_SP.factoryLead.vLead, 22 * CV.KPH_TO_MS, places=4)

    # no car: 254
    t += 20_000_000
    _, CS_SP = self._update(CI, [self._das_3(packer, True, 10), (0x1F5, DAS_4_NO_CAR, 2), (0x271, DAS_5_AT_23KPH, 2)], t)
    self.assertFalse(CS_SP.factoryLead.present)

  def test_not_present_when_the_factory_cruise_is_off(self):
    CI = self._interface(CAR.RAM_HD_5TH_GEN)
    packer = CANPacker(DBC[CAR.RAM_HD_5TH_GEN][Bus.pt])
    for i in range(5):
      _, CS_SP = self._update(CI, [self._das_3(packer, False, i), (0x1F5, DAS_4_AT_88M, 2), (0x271, DAS_5_AT_23KPH, 2)],
                              (i + 1) * 20_000_000)
    self.assertFalse(CS_SP.factoryLead.present)

  def test_das_5_never_marks_the_data_invalid(self):
    """DAS_5 has no counter or checksum on this truck; reading it must never make the camera bus invalid, whether its
    frames repeat the same counter or stop arriving."""
    CI = self._interface(CAR.RAM_HD_5TH_GEN)
    cp_cam = CI.can_parsers[Bus.cam]
    self.assertTrue(cp_cam.message_states[0x271].ignore_alive)
    sigs = {s.name for s in cp_cam.message_states[0x271].signals}
    self.assertNotIn("COUNTER", sigs)
    self.assertNotIn("CHECKSUM", sigs)

    t = 0
    for _ in range(200):  # four seconds of frames with a constant counter
      t += 20_000_000
      updated = cp_cam.update([(t, [(0x1F5, DAS_4_AT_88M, 2), (0x271, DAS_5_AT_23KPH, 2)])])
      self.assertIn(0x271, updated)
    self.assertEqual(cp_cam.message_states[0x271].counter_fail, 0)
    for _ in range(200):  # four seconds with DAS_5 missing
      t += 20_000_000
      cp_cam.update([(t, [(0x1F5, DAS_4_AT_88M, 2)])])
    self.assertTrue(cp_cam.message_states[0x271].valid(t, False))

  def test_other_rams_unchanged(self):
    CI = self._interface(CAR.RAM_1500_5TH_GEN)
    self.assertNotIn(0x271, CI.can_parsers[Bus.cam].message_states)
    _, CS_SP = self._update(CI, [(0x1F5, DAS_4_AT_88M, 2)], 20_000_000)
    self.assertFalse(CS_SP.factoryLead.present)
    self.assertEqual(CS_SP.factoryLead.dRel, 0.)


if __name__ == "__main__":
  unittest.main()
