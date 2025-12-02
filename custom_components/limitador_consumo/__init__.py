"""Soporte para Limitador de Consumo."""
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import callback
from homeassistant.const import STATE_ON
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity
from datetime import timedelta
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LimitadorBloqueoSwitch(ToggleEntity, RestoreEntity):
    """Entidad input_boolean para bloqueo de dispositivo del limitador."""
    
    def __init__(self, hass, device_entity_id: str):
        """Inicializar el switch de bloqueo."""
        self.hass = hass
        self._device_entity_id = device_entity_id
        device_name = device_entity_id.replace(".", "_")
        self._attr_unique_id = f"limitador_bloqueo_{device_name}"
        self._attr_name = f"Limitador {device_entity_id}"
        self._attr_icon = "mdi:lock"
        self._attr_is_on = False
        self._estado_personalizado = None  # Para climates: hvac_mode
        self.entity_id = f"{DOMAIN}.limitador_bloqueo_{device_name}"
        self._attr_should_poll = False
    
    @property
    def state(self):
        """Retornar el estado del bloqueo."""
        # Si está bloqueado y tiene estado personalizado (climate con hvac_mode), mostrar ese estado
        if self._attr_is_on and self._estado_personalizado:
            return self._estado_personalizado
        return STATE_ON if self._attr_is_on else "off"
    
    @property
    def device_info(self):
        """Return device info to link to integration."""
        return {
            "identifiers": {("limitador_consumo", self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "Limitador Consumo v3",
            "model": "Bloqueo Dispositivo",
        }
    
    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._attr_is_on
    
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._attr_is_on = True
        self.async_write_ha_state()
    
    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._attr_is_on = False
        self.async_write_ha_state()
    
    async def async_added_to_hass(self):
        """Restaurar el estado previo cuando se añade a HA."""
        await super().async_added_to_hass()
        
        # Restaurar estado anterior si existe
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # Restaurar el estado: si es "on" o "off", usar is_on normal
            # Si es otro valor (heat, cool, etc.), es un climate con estado personalizado
            if old_state.state in ("on", "off"):
                self._attr_is_on = old_state.state == "on"
                self._estado_personalizado = None
            else:
                # Es un hvac_mode guardado
                self._attr_is_on = True
                self._estado_personalizado = old_state.state
        else:
            self._attr_is_on = False
            self._estado_personalizado = None


async def _gestionar_bloqueo_dispositivo(hass, entry_id, entity_id, bloquear, estado_personalizado=None):
    """Gestiona el bloqueo/desbloqueo de un dispositivo y actualiza el estado.
    
    Args:
        hass: Instancia de Home Assistant
        entry_id: ID de la entrada de configuración
        entity_id: ID de la entidad a bloquear/desbloquear
        bloquear: True para bloquear, False para desbloquear
        estado_personalizado: Estado personalizado (ej: 'heat', 'cool' para climates)
    """
    bloqueados = hass.data["limitador_consumo"][entry_id]["dispositivos_bloqueados"]
    
    if bloquear:
        bloqueados.add(entity_id)
        _LOGGER.info(f"🔒 Dispositivo bloqueado: {entity_id} (estado: {estado_personalizado or 'ON'})")
    else:
        bloqueados.discard(entity_id)
        _LOGGER.info(f"🔓 Dispositivo desbloqueado: {entity_id}")
    
    # Actualizar el estado de la entidad de bloqueo directamente
    bloqueo_entities = hass.data["limitador_consumo"][entry_id].get("bloqueo_entities", [])
    for bloqueo_entity in bloqueo_entities:
        if bloqueo_entity._device_entity_id == entity_id:
            if bloquear:
                bloqueo_entity._attr_is_on = True
                # Para climates, guardar el hvac_mode como estado personalizado
                if estado_personalizado:
                    bloqueo_entity._estado_personalizado = estado_personalizado
            else:
                bloqueo_entity._attr_is_on = False
                bloqueo_entity._estado_personalizado = None
            bloqueo_entity.async_write_ha_state()
            estado_mostrado = estado_personalizado if (bloquear and estado_personalizado) else ('ON' if bloquear else 'OFF')
            _LOGGER.debug(f"✓ Estado actualizado: {bloqueo_entity.entity_id} = {estado_mostrado}")
            break
    
    # Disparar evento para que las automatizaciones puedan escucharlo
    hass.bus.async_fire(
        "limitador_consumo_bloqueo_changed",
        {
            "entity_id": entity_id,
            "bloqueado": bloquear
        }
    )

async def async_setup_entry(hass, entry):
    hass.data.setdefault("limitador_consumo", {})
    config = dict(entry.options) if entry.options else dict(entry.data)
    hass.data["limitador_consumo"][entry.entry_id] = {
        "config": config,
        "consumo_apagado": {},
        "dispositivos_bloqueados": set()  # Conjunto de dispositivos bloqueados
    }
    invertir_orden = config.get("invertir_orden_activacion", True)

    potencia_max = config["potencia"]
    sensor_potencia = config["sensor_potencia"]
    switches = config["switches_limitados"]
    intervalo_desactivacion = config["intervalo_desactivacion"]
    intervalo_activacion = config.get("intervalo_activacion", 60)
    climate_sensors = config.get("climate_power_sensors", {})  # Mapeo climate -> sensor de potencia
    notificaciones_activadas = config.get("notificaciones_activadas", True)  # Por defecto activadas

    apagados = hass.data["limitador_consumo"][entry.entry_id]["consumo_apagado"]
    bloqueados = hass.data["limitador_consumo"][entry.entry_id]["dispositivos_bloqueados"]
    
    _LOGGER.info(f"🚀 Limitador de Consumo: Inicializado")
    _LOGGER.info(f"  📊 Potencia máxima: {potencia_max}W")
    _LOGGER.info(f"  📡 Sensor de potencia: {sensor_potencia}")
    _LOGGER.info(f"  🔌 Dispositivos: {len(switches)} ({switches})")
    _LOGGER.info(f"  ⏱️ Intervalo desactivación: {intervalo_desactivacion}s")
    _LOGGER.info(f"  ⏱️ Intervalo activación: {intervalo_activacion}s")
    _LOGGER.info(f"  🔄 Invertir orden: {invertir_orden}")
    _LOGGER.info(f"  🔔 Notificaciones: {'Activadas' if notificaciones_activadas else 'Desactivadas'}")
    if climate_sensors:
        _LOGGER.info(f"  🌡️ Sensores de climates: {climate_sensors}")
    
    # Crear entidades de bloqueo
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_component import EntityComponent
    
    entity_registry = er.async_get(hass)
    
    # Limpiar entidades antiguas de input_boolean que ya no se usan
    for entity_id in switches:
        device_name = entity_id.replace(".", "_")
        unique_id = f"limitador_bloqueo_{device_name}"
        
        # Buscar y eliminar entidad antigua de input_boolean si existe
        old_input_boolean_id = f"input_boolean.{unique_id}"
        old_entry = entity_registry.async_get(old_input_boolean_id)
        if old_entry is not None:
            _LOGGER.info(f"🗑️ Eliminando entidad antigua: {old_input_boolean_id}")
            entity_registry.async_remove(old_input_boolean_id)
    
    # Crear o obtener el componente para las entidades de bloqueo
    component_key = f"{DOMAIN}_entities"
    if component_key not in hass.data:
        component = EntityComponent(_LOGGER, DOMAIN, hass)
        hass.data[component_key] = component
    else:
        component = hass.data[component_key]
    
    # Crear las entidades de bloqueo
    entities_to_add = []
    for entity_id in switches:
        bloqueo_switch = LimitadorBloqueoSwitch(hass, entity_id)
        entities_to_add.append(bloqueo_switch)
    
    # Añadir todas las entidades
    await component.async_add_entities(entities_to_add)
    
    # Guardar referencia a las entidades en hass.data para mantenerlas vivas
    hass.data["limitador_consumo"][entry.entry_id]["bloqueo_entities"] = entities_to_add
    
    _LOGGER.info(f"✓ {len(entities_to_add)} entidades de bloqueo creadas: {[e.entity_id for e in entities_to_add]}")

    @callback
    async def control_consumo(now):
        valor_potencia = hass.states.get(sensor_potencia)
        if (
            valor_potencia is None
            or valor_potencia.state in (None, "unknown", "unavailable", "")
        ):
            return

        try:
            potencia_actual = float(valor_potencia.state)
        except (ValueError, TypeError):
            return

        # Log cada verificación (reducido a debug para no llenar logs)
        _LOGGER.debug(f"⚡ control_consumo - Potencia: {potencia_actual}W / {potencia_max}W")
        
        # Apagar switches/climates si la potencia supera el límite
        # Apagar dispositivos en cascada si el consumo sigue siendo mayor al límite
        import asyncio
        while potencia_actual > potencia_max:
            _LOGGER.warning(f"🚨 EXCESO DE POTENCIA: {potencia_actual}W > {potencia_max}W - Iniciando apagado")
            apagado = False
            potencia_disparo = potencia_actual  # Guardar el valor de disparo
            for entity_id in switches:
                estado = hass.states.get(entity_id)
                domain = entity_id.split(".")[0]
                _LOGGER.debug(f"  🔍 Evaluando {entity_id}: estado={estado.state if estado else 'None'}, domain={domain}")
                if estado is not None:
                    if domain == "climate":
                        if estado.state != "off" and entity_id not in apagados:
                            # Verificar si tiene sensor de potencia asignado
                            climate_power_sensor = climate_sensors.get(entity_id)
                            consumo_climate = 0
                            
                            if climate_power_sensor:
                                estado_sensor = hass.states.get(climate_power_sensor)
                                if estado_sensor and estado_sensor.state not in (None, "unknown", "unavailable", ""):
                                    try:
                                        consumo_climate = float(estado_sensor.state)
                                        _LOGGER.info(f"  📊 Climate {entity_id} consumo actual: {consumo_climate}W")
                                    except (ValueError, TypeError):
                                        pass
                            
                            hvac_mode_actual = estado.attributes.get("hvac_mode")
                            apagados[entity_id] = {
                                "hvac_mode": hvac_mode_actual,
                                "temperature": estado.attributes.get("temperature"),
                                "preset_mode": estado.attributes.get("preset_mode"),
                                "fan_mode": estado.attributes.get("fan_mode"),
                                "consumo": consumo_climate
                            }
                            hass.bus.async_fire(
                                "limitador_consumo_climate_off",
                                {
                                    "climate": entity_id,
                                    "razon": "potencia_superior_al_limite",
                                    "potencia_actual": potencia_disparo,
                                    "potencia_max": potencia_max
                                }
                            )
                            if notificaciones_activadas:
                                await hass.services.async_call(
                                    "persistent_notification", "create",
                                    {
                                        "title": "Limitador de Consumo",
                                        "message": (
                                            f"El climate {entity_id} ha sido apagado por la integración "
                                            f"porque la potencia ({potencia_disparo}W) superó el límite ({potencia_max}W)."
                                        )
                                    },
                                    blocking=False
                                )
                            # Activar bloqueo del dispositivo ANTES de apagar, pasando el hvac_mode
                            await _gestionar_bloqueo_dispositivo(hass, entry.entry_id, entity_id, bloquear=True, estado_personalizado=hvac_mode_actual)
                            await hass.services.async_call(
                                "climate", "set_hvac_mode", 
                                {"entity_id": entity_id, "hvac_mode": "off"},
                                blocking=True
                            )
                            # Crear entrada en logbook con contexto propio
                            from homeassistant.core import Context
                            hass.bus.async_fire(
                                "logbook_entry",
                                {
                                    "name": f"Limitador de Consumo",
                                    "message": f"Apagado {entity_id}: Potencia excedida ({potencia_disparo}W > {potencia_max}W)",
                                    "entity_id": entity_id,
                                    "domain": "climate"
                                },
                                context=Context()
                            )
                            apagado = True
                            await asyncio.sleep(20)
                            break
                    elif domain == "switch":
                        if estado.state == STATE_ON and entity_id not in apagados:
                            switch_name = entity_id.split(".", 1)[1]
                            sensor_name = f"sensor.{switch_name}_potencia"
                            estado_sensor = hass.states.get(sensor_name)
                            consumo_dispositivo = 0
                            if estado_sensor and estado_sensor.state not in (None, "unknown", "unavailable", ""):
                                try:
                                    consumo = float(estado_sensor.state)
                                    apagados[entity_id] = consumo
                                    consumo_dispositivo = consumo
                                    potencia_actual -= consumo
                                except (ValueError, TypeError):
                                    apagados[entity_id] = 0
                            else:
                                apagados[entity_id] = 0
                            hass.bus.async_fire(
                                "limitador_consumo_switch_off",
                                {
                                    "switch": entity_id,
                                    "razon": "potencia_superior_al_limite",
                                    "potencia_actual": potencia_disparo,
                                    "potencia_max": potencia_max
                                }
                            )
                            if notificaciones_activadas:
                                await hass.services.async_call(
                                    "persistent_notification", "create",
                                    {
                                        "title": "Limitador de Consumo",
                                        "message": (
                                            f"El interruptor {entity_id} ha sido apagado por la integración "
                                            f"porque la potencia ({potencia_disparo}W) superó el límite ({potencia_max}W)."
                                        )
                                    },
                                    blocking=False
                                )
                            # Activar bloqueo del dispositivo ANTES de apagar
                            _LOGGER.info(f"🔴 Apagando switch {entity_id}...")
                            await _gestionar_bloqueo_dispositivo(hass, entry.entry_id, entity_id, bloquear=True)
                            _LOGGER.info(f"  📡 Llamando a switch.turn_off para {entity_id}")
                            await hass.services.async_call(
                                "switch", "turn_off", 
                                {"entity_id": entity_id},
                                blocking=True
                            )
                            # Crear entrada en logbook con contexto propio
                            from homeassistant.core import Context
                            hass.bus.async_fire(
                                "logbook_entry",
                                {
                                    "name": f"Limitador de Consumo",
                                    "message": f"Apagado {entity_id}: Potencia excedida ({potencia_disparo}W > {potencia_max}W)",
                                    "entity_id": entity_id,
                                    "domain": "switch"
                                },
                                context=Context()
                            )
                            _LOGGER.info(f"  ✅ Switch {entity_id} apagado")
                            apagado = True
                            await asyncio.sleep(20)
                            break
            if not apagado:
                # Si no se pudo apagar ningún dispositivo, salir del bucle
                break

    async def reactivar_dispositivos(now):
        _LOGGER.info(f"🔄 INICIO reactivar_dispositivos - Timestamp: {now}")
        valor_potencia = hass.states.get(sensor_potencia)
        if (
            valor_potencia is None
            or valor_potencia.state in (None, "unknown", "unavailable", "")
        ):
            _LOGGER.warning(f"⚠️ Sensor de potencia no disponible: {sensor_potencia}")
            return

        try:
            potencia_actual = float(valor_potencia.state)
        except (ValueError, TypeError):
            _LOGGER.warning(f"⚠️ Error al convertir potencia: {valor_potencia.state}")
            return

        _LOGGER.info(f"🔄 Verificando reactivación - Potencia actual: {potencia_actual}W / {potencia_max}W")
        _LOGGER.info(f"📋 Dispositivos apagados en memoria: {list(apagados.keys())}")
        _LOGGER.info(f"📋 Switches configurados: {switches}")
        
        # Primero verificar si hay dispositivos con limitador ON que no están en apagados
        # (puede pasar después de un reinicio de HA)
        _LOGGER.info(f"🔍 Verificando {len(switches)} dispositivos para detectar limitadores ON")
        for entity_id in switches:
            device_name = entity_id.replace(".", "_")
            limitador_entity_id = f"{DOMAIN}.limitador_bloqueo_{device_name}"
            limitador_state = hass.states.get(limitador_entity_id)
            
            _LOGGER.debug(f"   - {entity_id}: limitador={limitador_state.state if limitador_state else 'None'}")
            
            # El limitador está activo si no es "off" (puede ser "on", "heat", "cool", etc.)
            if limitador_state and limitador_state.state != "off":
                estado_dispositivo = hass.states.get(entity_id)
                _LOGGER.info(f"🔴 Limitador activo ({limitador_state.state}) para {entity_id}, estado dispositivo: {estado_dispositivo.state if estado_dispositivo else 'None'}")
                if estado_dispositivo and estado_dispositivo.state == "off":
                    # El limitador está activo y el dispositivo está OFF, pero no está en apagados
                    if entity_id not in apagados:
                        _LOGGER.warning(f"⚠️ Dispositivo {entity_id} encontrado con limitador activo pero no en lista de apagados (posible reinicio)")
                        # Añadirlo a apagados sin información de consumo
                        domain = entity_id.split(".")[0]
                        if domain == "climate":
                            # Para climate, guardar el hvac_mode del limitador y verificar sensor de potencia
                            hvac_mode_guardado = limitador_state.state if limitador_state.state != "on" else None
                            climate_power_sensor = climate_sensors.get(entity_id)
                            consumo = 0
                            if climate_power_sensor:
                                # Leer el consumo del sensor
                                estado_sensor = hass.states.get(climate_power_sensor)
                                if estado_sensor and estado_sensor.state not in (None, "unknown", "unavailable", ""):
                                    try:
                                        consumo = float(estado_sensor.state)
                                        _LOGGER.info(f"  📊 Climate {entity_id} consumo detectado: {consumo}W")
                                    except (ValueError, TypeError):
                                        pass
                            
                            # Guardar con hvac_mode si está disponible
                            if hvac_mode_guardado:
                                apagados[entity_id] = {"hvac_mode": hvac_mode_guardado, "consumo": consumo}
                                _LOGGER.info(f"  🌡️ Climate {entity_id} modo guardado: {hvac_mode_guardado}")
                            else:
                                apagados[entity_id] = {"consumo": consumo}
                        else:
                            # Para switch, intentar leer el sensor de potencia
                            switch_name = entity_id.split(".", 1)[1]
                            sensor_name = f"sensor.{switch_name}_potencia"
                            estado_sensor = hass.states.get(sensor_name)
                            if estado_sensor and estado_sensor.state not in (None, "unknown", "unavailable", ""):
                                try:
                                    consumo = float(estado_sensor.state)
                                    apagados[entity_id] = consumo
                                except (ValueError, TypeError):
                                    apagados[entity_id] = 0
                            else:
                                apagados[entity_id] = 0

        # Intentar reactivar switches apagados si el consumo lo permite
        switches_apagados = list(apagados.keys())
        # El orden invertido solo se aplica al reactivar
        if invertir_orden:
            switches_apagados = list(reversed(switches_apagados))
        
        _LOGGER.info(f"🔍 Intentando reactivar {len(switches_apagados)} dispositivos")
        
        for entity_id in switches_apagados:
            # Verificar si el limitador de bloqueo está activo (ON)
            device_name = entity_id.replace(".", "_")
            limitador_entity_id = f"{DOMAIN}.limitador_bloqueo_{device_name}"
            limitador_state = hass.states.get(limitador_entity_id)
            
            _LOGGER.debug(f"  📌 Procesando {entity_id}: limitador={limitador_state.state if limitador_state else 'None'}")
            
            # Solo intentar reactivar si el limitador está activo (no "off")
            # Para switches será "on", para climates será "heat", "cool", etc.
            if limitador_state is None or limitador_state.state == "off":
                _LOGGER.debug(f"  ⏭️ Saltando {entity_id} - limitador no está activo")
                continue
            
            estado = hass.states.get(entity_id)
            domain = entity_id.split(".")[0]
            apagado_info = apagados[entity_id]
            
            _LOGGER.debug(f"  🔍 {entity_id}: estado={estado.state if estado else 'None'}, domain={domain}, info={apagado_info}")
            
            if estado is not None and estado.state == "off":
                if domain == "climate":
                    # Verificar si tiene sensor de potencia asignado
                    climate_power_sensor = climate_sensors.get(entity_id)
                    puede_reactivar = True
                    
                    if climate_power_sensor:
                        # Tiene sensor de potencia, verificar si hay potencia disponible
                        consumo_climate = apagado_info if isinstance(apagado_info, (int, float)) else apagado_info.get("consumo", 0)
                        _LOGGER.info(f"  🌡️ Climate {entity_id} tiene sensor {climate_power_sensor}, consumo={consumo_climate}W")
                        
                        if consumo_climate > 0:
                            # Verificar potencia disponible
                            if potencia_actual + consumo_climate > potencia_max:
                                puede_reactivar = False
                                _LOGGER.info(f"  ⏸️ {entity_id} NO reactivado - no hay potencia ({potencia_actual}W + {consumo_climate}W > {potencia_max}W)")
                        else:
                            # Sin consumo registrado, usar margen del 80%
                            margen_80 = potencia_max * 0.8
                            if potencia_actual >= margen_80:
                                puede_reactivar = False
                                _LOGGER.info(f"  ⏸️ {entity_id} NO reactivado - potencia alta ({potencia_actual}W >= {margen_80}W)")
                    else:
                        # Sin sensor de potencia: reactivar solo si hay margen suficiente (80%)
                        margen_80 = potencia_max * 0.8
                        _LOGGER.info(f"  🌡️ Climate {entity_id} sin sensor de potencia - Potencia actual: {potencia_actual}W, Margen 80%: {margen_80}W")
                        if potencia_actual >= margen_80:
                            puede_reactivar = False
                            _LOGGER.info(f"  ⏸️ {entity_id} NO reactivado - potencia alta ({potencia_actual}W >= {margen_80}W)")
                    
                    if not puede_reactivar:
                        continue  # No reactivar ahora, intentar en la próxima iteración
                    
                    # Restaurar estado previo del climate
                    service_data = {"entity_id": entity_id}
                    
                    # Primero intentar obtener el hvac_mode del limitador
                    modo_restaurar = None
                    if limitador_state and limitador_state.state not in ("on", "off"):
                        # El limitador tiene un hvac_mode guardado (heat, cool, etc.)
                        modo_restaurar = limitador_state.state
                        _LOGGER.info(f"  🌡️ Usando modo del limitador: {modo_restaurar}")
                    
                    # Si no está en el limitador, buscar en apagados
                    if not modo_restaurar:
                        modo_restaurar = apagado_info.get("hvac_mode") if isinstance(apagado_info, dict) else None
                    
                    # Si no hay modo guardado, intentar obtenerlo del estado actual
                    if not modo_restaurar or modo_restaurar == "off":
                        estado_climate = hass.states.get(entity_id)
                        if estado_climate and hasattr(estado_climate, 'attributes'):
                            # Intentar con el último modo conocido o usar 'heat' por defecto
                            modos_disponibles = estado_climate.attributes.get("hvac_modes", [])
                            if "heat" in modos_disponibles:
                                modo_restaurar = "heat"
                            elif "cool" in modos_disponibles:
                                modo_restaurar = "cool"
                            elif "heat_cool" in modos_disponibles:
                                modo_restaurar = "heat_cool"
                            elif len(modos_disponibles) > 1:  # Tiene al menos un modo además de 'off'
                                modo_restaurar = [m for m in modos_disponibles if m != "off"][0]
                    
                    _LOGGER.info(f"  🌡️ Climate {entity_id}: modo_restaurar={modo_restaurar}, apagado_info={apagado_info}")
                    
                    if modo_restaurar and modo_restaurar != "off":
                        _LOGGER.info(f"  ▶️ Reactivando climate {entity_id} a modo {modo_restaurar}")
                        service_data["hvac_mode"] = modo_restaurar
                        # Desactivar bloqueo del dispositivo ANTES de encender
                        await _gestionar_bloqueo_dispositivo(hass, entry.entry_id, entity_id, bloquear=False)
                        await hass.services.async_call(
                            "climate", "set_hvac_mode", service_data,
                            blocking=True
                        )
                        # Crear entrada en logbook con contexto propio
                        from homeassistant.core import Context
                        hass.bus.async_fire(
                            "logbook_entry",
                            {
                                "name": f"Limitador de Consumo",
                                "message": f"Encendido {entity_id}: Potencia disponible ({potencia_actual}W / {potencia_max}W)",
                                "entity_id": entity_id,
                                "domain": "climate"
                            },
                            context=Context()
                        )
                        # Esperar a que el estado cambie
                        import asyncio
                        restaurado = False
                        for _ in range(5):
                            await asyncio.sleep(1)
                            estado_actual = hass.states.get(entity_id)
                            if estado_actual and estado_actual.state != "off":
                                restaurado = True
                                break
                        # Restaurar otros atributos si es necesario
                        if restaurado:
                            if apagado_info.get("temperature") is not None:
                                await hass.services.async_call(
                                    "climate", "set_temperature", {"entity_id": entity_id, "temperature": apagado_info["temperature"]},
                                    blocking=True
                                )
                            hass.bus.async_fire(
                                "limitador_consumo_climate_on",
                                {
                                    "climate": entity_id,
                                    "razon": "reactivacion",
                                    "potencia_actual": potencia_actual,
                                    "potencia_max": potencia_max
                                }
                            )
                            if notificaciones_activadas:
                                await hass.services.async_call(
                                    "persistent_notification", "create",
                                    {
                                        "title": "Limitador de Consumo",
                                        "message": (
                                            f"El climate {entity_id} ha sido encendido por la integración y restaurado a su estado previo."
                                        )
                                    },
                                    blocking=False
                                )
                            _LOGGER.info(f"  ✅ Climate {entity_id} reactivado correctamente")
                            apagados.pop(entity_id)
                            break  # Salir del bucle, solo reactiva uno a la vez
                        else:
                            if notificaciones_activadas:
                                await hass.services.async_call(
                                    "persistent_notification", "create",
                                    {
                                        "title": "Limitador de Consumo",
                                        "message": (
                                            f"El climate {entity_id} no pudo ser encendido correctamente."
                                        )
                                    },
                                    blocking=False
                                )
                            _LOGGER.warning(f"  ❌ Climate {entity_id} no pudo ser reactivado")
                            apagados.pop(entity_id)
                            continue  # No se pudo reactivar, continuar con el siguiente
                    else:
                        # No hay modo válido para restaurar, eliminar de apagados
                        _LOGGER.info(f"  ⏭️ Climate {entity_id} sin modo válido para restaurar, removiendo de lista")
                        apagados.pop(entity_id)
                        continue  # Continuar con el siguiente dispositivo
                else:
                    # Switch: verificar si hay suficiente potencia para reactivar
                    consumo_apagado = apagado_info
                    _LOGGER.info(f"  🔌 Switch {entity_id}: consumo={consumo_apagado}W, potencia_actual={potencia_actual}W")
                    
                    if consumo_apagado == 0 or consumo_apagado is None:
                        # Sin sensor de potencia: reactivar solo si hay margen suficiente
                        margen_80 = potencia_max * 0.8
                        _LOGGER.info(f"    Sin sensor - Potencia actual: {potencia_actual}W, Margen 80%: {margen_80}W")
                        if potencia_actual < margen_80:
                            _LOGGER.info(f"  ▶️ Reactivando {entity_id} (sin sensor, hay margen)")
                            hass.bus.async_fire(
                                "limitador_consumo_switch_on",
                                {
                                    "switch": entity_id,
                                    "razon": "sin_sensor_potencia",
                                    "potencia_actual": potencia_actual,
                                    "potencia_max": potencia_max
                                }
                            )
                            if notificaciones_activadas:
                                await hass.services.async_call(
                                    "persistent_notification", "create",
                                    {
                                        "title": "Limitador de Consumo",
                                        "message": (
                                            f"El interruptor {entity_id} ha sido encendido por la integración "
                                            f"porque no tiene sensor de potencia propio."
                                        )
                                    },
                                    blocking=False
                                )
                            # Desactivar bloqueo del dispositivo ANTES de encender
                            await _gestionar_bloqueo_dispositivo(hass, entry.entry_id, entity_id, bloquear=False)
                            await hass.services.async_call(
                                "switch", "turn_on", {"entity_id": entity_id},
                                blocking=True
                            )
                            # Crear entrada en logbook con contexto propio
                            from homeassistant.core import Context
                            hass.bus.async_fire(
                                "logbook_entry",
                                {
                                    "name": f"Limitador de Consumo",
                                    "message": f"Encendido {entity_id}: Hay margen de potencia ({potencia_actual}W < 80% de {potencia_max}W)",
                                    "entity_id": entity_id,
                                    "domain": "switch"
                                },
                                context=Context()
                            )
                            _LOGGER.info(f"  ✅ Switch {entity_id} reactivado")
                            apagados.pop(entity_id)
                            break  # Reactivado, salir del bucle
                        else:
                            _LOGGER.info(f"  ⏸️ {entity_id} NO reactivado - potencia alta ({potencia_actual}W >= {margen_80}W)")
                            continue  # No hay margen, continuar con el siguiente
                    elif potencia_actual + consumo_apagado <= potencia_max:
                        # Con sensor: verificar que hay suficiente potencia
                        _LOGGER.info(f"  ▶️ Reactivando {entity_id} (con sensor, {potencia_actual}W + {consumo_apagado}W <= {potencia_max}W)")
                        hass.bus.async_fire(
                            "limitador_consumo_switch_on",
                            {
                                "switch": entity_id,
                                "razon": "potencia_dentro_del_limite",
                                "potencia_actual": potencia_actual,
                                "potencia_max": potencia_max
                            }
                        )
                        if notificaciones_activadas:
                            await hass.services.async_call(
                                "persistent_notification", "create",
                                {
                                    "title": "Limitador de Consumo",
                                    "message": (
                                        f"El interruptor {entity_id} ha sido encendido por la integración "
                                        f"porque la potencia ({potencia_actual}W + {consumo_apagado}W) permite reactivarlo."
                                    )
                                },
                                blocking=False
                            )
                        # Desactivar bloqueo del dispositivo ANTES de encender
                        await _gestionar_bloqueo_dispositivo(hass, entry.entry_id, entity_id, bloquear=False)
                        await hass.services.async_call(
                            "switch", "turn_on", {"entity_id": entity_id},
                            blocking=True
                        )
                        # Crear entrada en logbook con contexto propio
                        from homeassistant.core import Context
                        hass.bus.async_fire(
                            "logbook_entry",
                            {
                                "name": f"Limitador de Consumo",
                                "message": f"Encendido {entity_id}: Potencia disponible ({potencia_actual}W + {consumo_apagado}W ≤ {potencia_max}W)",
                                "entity_id": entity_id,
                                "domain": "switch"
                            },
                            context=Context()
                        )
                        _LOGGER.info(f"  ✅ Switch {entity_id} reactivado")
                        apagados.pop(entity_id)
                        break  # Reactivado, salir del bucle
                    else:
                        _LOGGER.info(f"  ⏸️ {entity_id} NO reactivado - no hay potencia suficiente ({potencia_actual}W + {consumo_apagado}W > {potencia_max}W)")
                        continue  # No hay potencia, continuar con el siguiente
        
        _LOGGER.info(f"✅ FIN reactivar_dispositivos - Dispositivos restantes en apagados: {list(apagados.keys())}")

    # Programa la comprobación periódica para apagar y reactivar
    hass.data["limitador_consumo"][entry.entry_id]["listener_desactivar"] = async_track_time_interval(
        hass, control_consumo, timedelta(seconds=intervalo_desactivacion)
    )
    hass.data["limitador_consumo"][entry.entry_id]["listener_activar"] = async_track_time_interval(
        hass, reactivar_dispositivos, timedelta(seconds=intervalo_activacion)
    )
    
    _LOGGER.info(f"✅ Listeners registrados - control_consumo cada {intervalo_desactivacion}s, reactivar_dispositivos cada {intervalo_activacion}s")

    return True

async def async_unload_entry(hass, entry):
    """Descargar una entrada de configuración."""
    # Cancelar los listeners
    if "listener_desactivar" in hass.data["limitador_consumo"][entry.entry_id]:
        hass.data["limitador_consumo"][entry.entry_id]["listener_desactivar"]()
    if "listener_activar" in hass.data["limitador_consumo"][entry.entry_id]:
        hass.data["limitador_consumo"][entry.entry_id]["listener_activar"]()
    
    # Descargar el componente de entidades si existe
    component_key = f"{DOMAIN}_entities"
    if component_key in hass.data:
        component = hass.data[component_key]
        await component.async_unload_entry(entry)
    
    # Limpiar datos
    hass.data["limitador_consumo"].pop(entry.entry_id)
    
    _LOGGER.info("Limitador de Consumo: Integración descargada correctamente")
    return True