from homeassistant import config_entries
import voluptuous as vol
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_POTENCIA, CONF_SENSOR, CONF_SWITCHES

CONF_INTERVALO_DESACTIVACION = "intervalo_desactivacion"
CONF_INTERVALO_ACTIVACION = "intervalo_activacion"
CONF_INVERTIR_ORDEN = "invertir_orden_activacion"
CONF_CLIMATE_SENSORS = "climate_power_sensors"  # Mapeo climate -> sensor de potencia

class LimitadorConsumoV3ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    def __init__(self):
        self.config_data = {}
    
    async def async_step_user(self, user_input=None):
        errors = {}

        # Limitar a una sola entrada
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Permitir seleccionar switches y climates
        schema = vol.Schema({
            vol.Required(CONF_POTENCIA, default=4600): vol.Coerce(float),
            vol.Required(CONF_SENSOR): selector.selector({
                "entity": {
                    "domain": "sensor",
                    "device_class": "power"
                }
            }),
            vol.Required(CONF_INTERVALO_DESACTIVACION, default=32): vol.Coerce(int),
            vol.Required(CONF_INTERVALO_ACTIVACION, default=45): vol.Coerce(int),
            vol.Required(CONF_SWITCHES): selector.selector({
                "entity": {
                    "domain": ["switch", "climate"],
                    "multiple": True
                }
            }),
            vol.Required(CONF_INVERTIR_ORDEN, default=False): vol.Coerce(bool),
            vol.Required("notificaciones_activadas", default=True): vol.Coerce(bool)
        })

        if user_input is not None:
            potencia = user_input.get(CONF_POTENCIA)
            sensor = user_input.get(CONF_SENSOR)
            switches = user_input.get(CONF_SWITCHES)
            intervalo_desactivacion = user_input.get(CONF_INTERVALO_DESACTIVACION)
            intervalo_activacion = user_input.get(CONF_INTERVALO_ACTIVACION)
            invertir_orden = user_input.get(CONF_INVERTIR_ORDEN, False)
            if potencia is None or potencia <= 0:
                errors["base"] = "invalid_potencia"
            elif not sensor:
                errors["base"] = "invalid_sensor"
            elif not switches or len(switches) == 0:
                errors["base"] = "invalid_switches"
            elif intervalo_desactivacion is None or intervalo_desactivacion < 1:
                errors["base"] = "invalid_intervalo_desactivacion"
            elif intervalo_activacion is None or intervalo_activacion < 1:
                errors["base"] = "invalid_intervalo_activacion"
            else:
                # Guardar datos y pasar al siguiente paso si hay climates
                self.config_data = user_input
                # Asegurar que notificaciones_activadas esté guardado
                if "notificaciones_activadas" not in self.config_data:
                    self.config_data["notificaciones_activadas"] = True
                climates = [s for s in switches if s.startswith("climate.")]
                if climates:
                    return await self.async_step_climate_sensors()
                else:
                    # No hay climates, crear entrada directamente
                    self.config_data[CONF_CLIMATE_SENSORS] = {}
                    return self.async_create_entry(
                        title="Limitador de Consumo",
                        data=self.config_data
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )
    
    async def async_step_climate_sensors(self, user_input=None):
        """Segundo paso: asignar sensores de potencia a climates"""
        errors = {}
        
        switches = self.config_data.get(CONF_SWITCHES, [])
        climates = [s for s in switches if s.startswith("climate.")]
        
        if user_input is not None:
            # Guardar el mapeo de climates a sensores (solo los que tienen valor válido)
            # Filtrar valores vacíos, None, strings vacías y 'ninguno'
            climate_sensors_map = {
                k: v for k, v in user_input.items() 
                if v and (v.strip() if isinstance(v, str) else True) and v.lower() != 'ninguno'
            }
            self.config_data[CONF_CLIMATE_SENSORS] = climate_sensors_map
            return self.async_create_entry(
                title="Limitador de Consumo",
                data=self.config_data
            )
        
        # Crear un campo para cada climate con opción 'ninguno'
        # Obtener todos los sensores de potencia disponibles
        power_sensors = []
        for state in self.hass.states.async_all():
            if state.domain == "sensor" and state.attributes.get("device_class") == "power":
                power_sensors.append(state.entity_id)
        
        schema_dict = {}
        for climate in climates:
            # Lista de opciones: 'ninguno' + sensores disponibles
            options = ["ninguno"] + power_sensors
            schema_dict[vol.Optional(climate, default="ninguno")] = vol.In(options)
        
        return self.async_show_form(
            step_id="climate_sensors",
            data_schema=vol.Schema(schema_dict),
            errors=errors
        )

    def async_get_entry_title(self, data):
        potencia = data.get(CONF_POTENCIA, "N/A")
        sensor = data.get(CONF_SENSOR, "N/A")
        switches = data.get(CONF_SWITCHES, [])
        switches_str = ", ".join(switches) if switches else "N/A"
        intervalo_desactivacion = data.get(CONF_INTERVALO_DESACTIVACION, "N/A")
        intervalo_activacion = data.get(CONF_INTERVALO_ACTIVACION, "N/A")
        invertir_orden = data.get(CONF_INVERTIR_ORDEN, False)
        invertir_str = "Invertido" if invertir_orden else "Normal"
        return (f"Potencia contratada: {potencia} kW | Sensor de consumo total: {sensor} | "
            f"Desactivación: {intervalo_desactivacion}s | Activación: {intervalo_activacion}s | Switches: {switches_str} | Orden: {invertir_str}")

    @staticmethod
    def async_get_options_flow(config_entry):
        return LimitadorConsumoV3OptionsFlowHandler(config_entry)

class LimitadorConsumoV3OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.options_data = {}

    async def async_step_init(self, user_input=None):
        errors = {}

        current_potencia = self.config_entry.options.get(CONF_POTENCIA, self.config_entry.data.get(CONF_POTENCIA, 4.6))
        current_sensor = self.config_entry.options.get(CONF_SENSOR, self.config_entry.data.get(CONF_SENSOR, ""))
        current_switches = self.config_entry.options.get(CONF_SWITCHES, self.config_entry.data.get(CONF_SWITCHES, []))
        current_intervalo_desactivacion = self.config_entry.options.get(CONF_INTERVALO_DESACTIVACION, self.config_entry.data.get(CONF_INTERVALO_DESACTIVACION, 10))
        current_intervalo_activacion = self.config_entry.options.get(CONF_INTERVALO_ACTIVACION, self.config_entry.data.get(CONF_INTERVALO_ACTIVACION, 10))
        current_invertir_orden = self.config_entry.options.get(CONF_INVERTIR_ORDEN, self.config_entry.data.get(CONF_INVERTIR_ORDEN, False))
        current_notificaciones = self.config_entry.options.get("notificaciones_activadas", self.config_entry.data.get("notificaciones_activadas", True))

        schema = vol.Schema({
            vol.Required(CONF_POTENCIA, default=current_potencia): vol.Coerce(float),
            vol.Required(CONF_SENSOR, default=current_sensor): selector.selector({
                "entity": {
                    "domain": "sensor",
                    "device_class": "power"
                }
            }),
            vol.Required(CONF_INTERVALO_DESACTIVACION, default=current_intervalo_desactivacion): vol.Coerce(int),
            vol.Required(CONF_INTERVALO_ACTIVACION, default=current_intervalo_activacion): vol.Coerce(int),
            vol.Required(CONF_SWITCHES, default=current_switches): selector.selector({
                "entity": {
                    "domain": ["switch", "climate"],
                    "multiple": True
                }
            }),
            vol.Required(CONF_INVERTIR_ORDEN, default=current_invertir_orden): vol.Coerce(bool),
            vol.Required("notificaciones_activadas", default=current_notificaciones): vol.Coerce(bool)
        })

        if user_input is not None:
            potencia = user_input.get(CONF_POTENCIA)
            sensor = user_input.get(CONF_SENSOR)
            switches = user_input.get(CONF_SWITCHES)
            intervalo_desactivacion = user_input.get(CONF_INTERVALO_DESACTIVACION)
            intervalo_activacion = user_input.get(CONF_INTERVALO_ACTIVACION)
            invertir_orden = user_input.get(CONF_INVERTIR_ORDEN, False)
            if potencia is None or potencia <= 0:
                errors["base"] = "invalid_potencia"
            elif not sensor:
                errors["base"] = "invalid_sensor"
            elif not switches or len(switches) == 0:
                errors["base"] = "invalid_switches"
            elif intervalo_desactivacion is None or intervalo_desactivacion < 1:
                errors["base"] = "invalid_intervalo_desactivacion"
            elif intervalo_activacion is None or intervalo_activacion < 1:
                errors["base"] = "invalid_intervalo_activacion"
            else:
                # Guardar datos y pasar al siguiente paso si hay climates
                self.options_data = user_input
                climates = [s for s in switches if s.startswith("climate.")]
                if climates:
                    return await self.async_step_climate_sensors()
                else:
                    # No hay climates, guardar opciones directamente
                    self.options_data[CONF_CLIMATE_SENSORS] = {}
                    return self.async_create_entry(title="", data=self.options_data)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors
        )
    
    async def async_step_climate_sensors(self, user_input=None):
        """Segundo paso: asignar sensores de potencia a climates"""
        errors = {}
        
        switches = self.options_data.get(CONF_SWITCHES, [])
        climates = [s for s in switches if s.startswith("climate.")]
        current_climate_sensors = self.config_entry.options.get(CONF_CLIMATE_SENSORS, self.config_entry.data.get(CONF_CLIMATE_SENSORS, {}))
        
        if user_input is not None:
            # Guardar el mapeo de climates a sensores (solo los que tienen valor válido)
            # Filtrar valores vacíos, None, strings vacías y 'ninguno'
            climate_sensors_map = {
                k: v for k, v in user_input.items() 
                if v and (v.strip() if isinstance(v, str) else True) and v.lower() != 'ninguno'
            }
            self.options_data[CONF_CLIMATE_SENSORS] = climate_sensors_map
            return self.async_create_entry(title="", data=self.options_data)
        
        # Crear un campo para cada climate con opción 'ninguno'
        # Obtener todos los sensores de potencia disponibles
        power_sensors = []
        for state in self.hass.states.async_all():
            if state.domain == "sensor" and state.attributes.get("device_class") == "power":
                power_sensors.append(state.entity_id)
        
        schema_dict = {}
        for climate in climates:
            default_sensor = current_climate_sensors.get(climate, "ninguno")
            # Si el default no está en las opciones, usar 'ninguno'
            if default_sensor and default_sensor not in power_sensors:
                # Verificar si el sensor existe aún
                if self.hass.states.get(default_sensor) is None:
                    default_sensor = "ninguno"
            elif not default_sensor:
                default_sensor = "ninguno"
            
            # Lista de opciones: 'ninguno' + sensores disponibles
            options = ["ninguno"] + power_sensors
            schema_dict[vol.Optional(climate, default=default_sensor)] = vol.In(options)
        
        return self.async_show_form(
            step_id="climate_sensors",
            data_schema=vol.Schema(schema_dict),
            errors=errors
        )
