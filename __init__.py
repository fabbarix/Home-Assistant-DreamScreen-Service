"""Adds a service to Home Assistant to control DreamScreen wifi models."""
import asyncio
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_ENTITY_ID, CONF_MODE, CONF_BRIGHTNESS)
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent

REQUIREMENTS = ["pydreamscreen>=0.0.6"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'dreamscreen'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_MODE = 'set_mode'
SERVICE_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_MODE): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
})

SERVICE_HDMI_SOURCE = 'set_hdmi_source'
CONF_HDMI_SOURCE = 'source'
SERVICE_HDMI_SOURCE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_HDMI_SOURCE): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
})

SERVICE_BRIGHTNESS = 'set_brightness'
SERVICE_BRIGHTNESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
})

SERVICE_AMBIENT_SCENE = 'set_ambient_scene'
CONF_AMBIENT_SCENE = 'scene'
SERVICE_AMBIENT_SCENE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_AMBIENT_SCENE): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
})

SERVICE_AMBIENT_COLOR = 'set_ambient_color'
CONF_AMBIENT_COLOR = 'color'
SERVICE_AMBIENT_COLOR_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_AMBIENT_COLOR): vol.Match(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
})

SERVICE_TO_ATTRIBUTE = {
    SERVICE_MODE: {
        'attribute': 'mode',
        'schema': SERVICE_MODE_SCHEMA,
        'param': CONF_MODE,
    },
    SERVICE_HDMI_SOURCE: {
        'attribute': 'hdmi_input',
        'schema': SERVICE_HDMI_SOURCE_SCHEMA,
        'param': CONF_HDMI_SOURCE,
    },
    SERVICE_BRIGHTNESS: {
        'attribute': 'brightness',
        'schema': SERVICE_BRIGHTNESS_SCHEMA,
        'param': CONF_BRIGHTNESS,
    },
    SERVICE_AMBIENT_SCENE: {
        'attribute': 'ambient_scene',
        'schema': SERVICE_AMBIENT_SCENE_SCHEMA,
        'param': CONF_AMBIENT_SCENE,
    },
    SERVICE_AMBIENT_COLOR: {
        'attribute': 'ambient_color',
        'schema': SERVICE_AMBIENT_COLOR_SCHEMA,
        'param': CONF_AMBIENT_COLOR,
    },
}


@asyncio.coroutine
def async_setup(hass, config):
    """Setup DreamScreen."""
    import pydreamscreen

    config = config.get(DOMAIN, {})

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    @asyncio.coroutine
    def async_handle_dreamscreen_services(service):
        """Reusable DreamScreen service caller."""
        service_definition = SERVICE_TO_ATTRIBUTE.get(service.service)

        attribute = service_definition['attribute']
        attribute_value = service.data.get(service_definition['param'])

        target_entities = yield from component.async_extract_from_service(service)

        updates = []
        for entity in target_entities:
            _LOGGER.debug("setting {} {} to {}".format(
                entity.entity_id,
                attribute,
                attribute_value
            ))
            setattr(entity.device, attribute, attribute_value)
            updates.append(entity.async_update_ha_state(True))

        if updates:
            yield from asyncio.wait(updates, loop=hass.loop)

    for service_name in SERVICE_TO_ATTRIBUTE:
        schema = SERVICE_TO_ATTRIBUTE[service_name].get('schema')
        hass.services.async_register(DOMAIN,
                                     service_name,
                                     async_handle_dreamscreen_services,
                                     schema=schema)

    entities = []
    entity_ids = []
    for device in pydreamscreen.get_devices():
        entity = DreamScreenEntity(device=device,
                                   current_ids=entity_ids)
        entity_ids.append(entity.entity_id)
        entities.append(entity)

    yield from component.async_add_entities(entities)
    return True


class DreamScreenEntity(Entity):
    """Wraps DreamScreen in a Home Assistant entity."""

    def __init__(self, device, current_ids):
        """Initialize state & entity properties."""
        self.device = device
        self.entity_id = generate_entity_id(entity_id_format=ENTITY_ID_FORMAT,
                                            name=self.device.name,
                                            current_ids=current_ids)
        self._name = self.device.name

    @property
    def name(self):
        """Device friendly name from DreamScreen device."""
        return self._name

    @property
    def state(self) -> str:
        """Assume turned on if mode is truthy."""
        return "on" if self.device.mode else 'off'

    @property
    def assumed_state(self):
        """If not responding, assume device is off."""
        return 'off'

    @property
    def state_attributes(self):
        """Expose DreamScreen device attributes as state properties."""
        import pydreamscreen
        attrs = {
            'group_name': self.device.group_name,
            'group_number': self.device.group_number,
            'device_mode': self.device.mode,
            'brightness': self.device.brightness,
            'ambient_color': "#" + self.device.ambient_color.hex().upper(),
            'ambient_scene': self.device.ambient_scene
        }

        if isinstance(self.device, (pydreamscreen.DreamScreenHD,
                                    pydreamscreen.DreamScreen4K)):
            selected_hdmi = None  # type: str
            if self.device.hdmi_input == 0:
                selected_hdmi = self.device.hdmi_input_1_name
            elif self.device.hdmi_input == 1:
                selected_hdmi = self.device.hdmi_input_2_name
            elif self.device.hdmi_input == 2:
                selected_hdmi = self.device.hdmi_input_3_name
            attrs.update({
                'selected_hdmi': selected_hdmi,
                'hdmi_input': self.device.hdmi_input,
                'hdmi_input_1_name': self.device.hdmi_input_1_name,
                'hdmi_input_2_name': self.device.hdmi_input_2_name,
                'hdmi_input_3_name': self.device.hdmi_input_3_name,
                'hdmi_active_channels': self.device.hdmi_active_channels,
            })

        return attrs

    def update(self):
        """When updating entity, call update on the device."""
        self.device.update_current_state()
