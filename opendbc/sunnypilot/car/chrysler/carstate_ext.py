
"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

from enum import StrEnum

from opendbc.car import Bus, structs
from opendbc.can.parser import CANParser
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.chrysler.values import RAM_HD
from opendbc.sunnypilot.car.chrysler.values_ext import BUTTONS


class CarStateExt:
  def __init__(self, CP, CP_SP):
    self.CP = CP
    self.CP_SP = CP_SP

    self.button_events = []
    self.button_states = {button.event_type: False for button in BUTTONS}

  def update(self, ret: structs.CarState, ret_sp: structs.CarStateSP, can_parsers: dict[StrEnum, CANParser]):
    cp = can_parsers[Bus.pt]

    button_events = []
    for button in BUTTONS:
      state = (cp.vl[button.can_addr][button.can_msg] in button.values)
      if self.button_states[button.event_type] != state:
        event = structs.CarState.ButtonEvent.new_message()
        event.type = button.event_type
        event.pressed = state
        button_events.append(event)
      self.button_states[button.event_type] = state
    self.button_events = button_events

    if self.CP.carFingerprint in RAM_HD:
      ret.steeringAngleDeg = cp.vl["STEERING"]["STEERING_ANGLE"]

      # The windshield unit's own car (edfrahm/SP-RamHD-TICI-Port#6, #28), read only: DAS_4 LEAD_DISTANCE in meters
      # (254 = no car) and DAS_5 LEAD_SPEED_KPH (capped at the set speed). Both are filled in only while the factory
      # cruise control is engaged.
      cp_cam = can_parsers[Bus.cam]
      lead_distance = cp_cam.vl["DAS_4"]["LEAD_DISTANCE"]
      ret_sp.factoryLead.present = bool(ret.cruiseState.enabled and lead_distance < 254)
      ret_sp.factoryLead.dRel = float(lead_distance)
      ret_sp.factoryLead.vLead = float(cp_cam.vl["DAS_5"]["LEAD_SPEED_KPH"] * CV.KPH_TO_MS)
