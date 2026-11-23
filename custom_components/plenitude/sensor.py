"""Sensors: the last day with data, its consumption and its cost (energy, costs per kWh and percentages on them, no
periodic costs).

They have no ``state_class`` on purpose: the history is in the imported statistics, and a sensor with a
state class would produce a second, misplaced copy (the values refer to two days ago).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SUPPLY, DOMAIN
from .coordinator import CURRENCY, PlenitudeConfigEntry, PlenitudeCoordinator, PlenitudeData
from .texts import text


@dataclass(frozen=True, kw_only=True)
class PlenitudeSensorDescription(SensorEntityDescription):
    value: Callable[[PlenitudeData], float | date | None]
    needs_cost: bool = False


SENSORS = (
    PlenitudeSensorDescription(
        key="ultimo_giorno",
        translation_key="ultimo_giorno",
        device_class=SensorDeviceClass.DATE,
        value=lambda data: data.last_day,
    ),
    PlenitudeSensorDescription(
        key="consumo_ultimo_giorno",
        translation_key="consumo_ultimo_giorno",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda data: data.last_day_kwh,
    ),
    PlenitudeSensorDescription(
        key="costo_ultimo_giorno",
        translation_key="costo_ultimo_giorno",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value=lambda data: data.last_day_cost,
        needs_cost=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PlenitudeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        PlenitudeSensor(coordinator, description)
        for description in SENSORS
        if coordinator.has_cost or not description.needs_cost
    )


class PlenitudeSensor(CoordinatorEntity[PlenitudeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: PlenitudeSensorDescription

    def __init__(self, coordinator: PlenitudeCoordinator, description: PlenitudeSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        key = coordinator.config_entry.data[CONF_SUPPLY]
        self._attr_unique_id = f"{key}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            name=coordinator.config_entry.title,
            manufacturer="Eni Plenitude",
            model=text(coordinator.language, "model"),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | date | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value(self.coordinator.data)
