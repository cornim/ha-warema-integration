import logging
from datetime import datetime, timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import (
    CoverEntity, DEVICE_CLASS_SHADE, SUPPORT_OPEN, SUPPORT_CLOSE,
    SUPPORT_SET_POSITION, ATTR_POSITION, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

#TODO Should be moved to homeassistant.const
CONF_WEBCONTROL_SERVER_ADDR = 'webcontrol_server_addr'
CONF_UPDATE_INTERVAL = 'update_interval'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_WEBCONTROL_SERVER_ADDR, default='http://webcontrol.local'): cv.url,
    vol.Optional(CONF_UPDATE_INTERVAL, default=600): cv.positive_int
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    from warema_wms import Shade, WmsController
    shades = Shade.get_all_shades(WmsController(config[CONF_WEBCONTROL_SERVER_ADDR]), time_between_cmds=0.5)
    add_devices(WaremaShade(s, config[CONF_UPDATE_INTERVAL]) for s in shades)


class WaremaShade(CoverEntity):
    """Represents a warema shade"""

    def __init__(self, shade, update_interval: int):
        self.shade = shade
        self.room = shade.get_room_name()
        self.channel = shade.get_channel_name()
        self.position = 0
        self.last_position = self.position
        self.is_moving = False
        self.state_last_updated = datetime.now()
        self.next_state_upate = datetime.now()
        '''This is needed because, when a move is triggered by HA, sometimes the next status update
        still reports 'not moving' because shitty warema hasn't caught up with reality yet
        and then the next update is delayed until for update_interval seconds'''
        self.force_update_until = datetime.now()
        self.update_interval = update_interval

    def update(self, force=False):
        if datetime.now() > self.next_state_upate or self.is_moving\
                or datetime.now() < self.force_update_until or force:
            self.last_position = self.position
            self.position, self.is_moving, self.state_last_updated = \
                self.shade.get_shade_state(True)
            if self.state_last_updated:
                self.next_state_upate = \
                    self.state_last_updated \
                    + timedelta(seconds=self.update_interval)
            _LOGGER.debug('Update performed for {}'.format(self.name))
        else:
            _LOGGER.debug('Update skipped for {}. Next update {}'
                          .format(self.name, self.next_state_upate))

    @property
    def device_class(self):
        return DEVICE_CLASS_SHADE

    @property
    def supported_features(self):
        return SUPPORT_OPEN|SUPPORT_CLOSE|SUPPORT_SET_POSITION

    @property
    def unique_id(self):
        return 'warema_shade' + self.name

    @property
    def name(self):
        return "{}:{}".format(self.room, self.channel)

    @property
    def current_cover_position(self):
        return 100 - self.position

    @property
    def is_opening(self):
        if self.is_moving and self.last_position > self.position:
            return True
        else:
            return False

    @property
    def is_closing(self):
        if self.is_moving and self.last_position < self.position:
            return True
        else:
            return False

    @property
    def is_closed(self):
        if not self.is_moving and self.position == 100:
            return True
        else:
            return False

    def open_cover(self, **kwargs):
        self.force_update_until = datetime.now() + timedelta(seconds=15)
        self.shade.set_shade_position(0)

    def close_cover(self, **kwargs):
        self.force_update_until = datetime.now() + timedelta(seconds=15)
        self.shade.set_shade_position(100)

    def set_cover_position(self, **kwargs):
        self.force_update_until = datetime.now() + timedelta(seconds=15)
        self.shade.set_shade_position(100 - kwargs[ATTR_POSITION])

