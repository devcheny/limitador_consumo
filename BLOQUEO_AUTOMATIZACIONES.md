# Sistema de Bloqueo de Dispositivos - Limitador de Consumo

## ¿Cómo funciona?

Cuando el **Limitador de Consumo v3** apaga un dispositivo por exceso de potencia, lo marca internamente como "bloqueado". Este bloqueo permanece activo hasta que la propia integración decide reactivar el dispositivo automáticamente.

## Evitar que automatizaciones enciendan dispositivos bloqueados

### Método 1: Escuchar el evento de bloqueo

La integración dispara eventos cada vez que un dispositivo es bloqueado o desbloqueado:

**Evento:** `limitador_consumo_bloqueo_changed`

**Datos del evento:**
- `entity_id`: El dispositivo que cambió de estado
- `bloqueado`: `true` si está bloqueado, `false` si está desbloqueado

#### Ejemplo de automatización que respeta el bloqueo:

```yaml
automation:
  - alias: "Encender calefactor - con protección limitador"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      # Tu automatización solo se ejecuta si el limitador NO ha bloqueado el dispositivo
      - condition: template
        value_template: >
          {% set bloqueados = state_attr('sensor.limitador_dispositivos_bloqueados', 'dispositivos') | default([]) %}
          {{ 'switch.calefactor_salon' not in bloqueados }}
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.calefactor_salon
```

### Método 2: Crear un helper manualmente

Puedes crear manualmente helpers `input_boolean` para cada dispositivo:

1. Ve a **Configuración** → **Dispositivos y Servicios** → **Helpers**
2. Crea un **Alternar** (Toggle/Input Boolean)
3. Nómbralo: `limitador_bloqueo_switch_nombre_dispositivo`
4. Luego crea esta automatización para sincronizarlo:

```yaml
automation:
  - alias: "Sincronizar bloqueo con helper"
    trigger:
      - platform: event
        event_type: limitador_consumo_bloqueo_changed
    action:
      - service: >
          {% if trigger.event.data.bloqueado %}
            input_boolean.turn_on
          {% else %}
            input_boolean.turn_off
          {% endif %}
        target:
          entity_id: >
            input_boolean.limitador_bloqueo_{{ trigger.event.data.entity_id.replace('.', '_') }}
```

Después, en tus automatizaciones:

```yaml
automation:
  - alias: "Encender dispositivo - verificar bloqueo"
    trigger:
      - platform: ...
    condition:
      - condition: state
        entity_id: input_boolean.limitador_bloqueo_switch_calefactor_salon
        state: 'off'  # Solo si NO está bloqueado
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.calefactor_salon
```

## Consultar dispositivos bloqueados en tiempo real

Puedes verificar qué dispositivos están bloqueados consultando:

```yaml
{{ state_attr('limitador_consumo', 'dispositivos_bloqueados') }}
```

O usar este template sensor:

```yaml
template:
  - sensor:
      - name: "Limitador Dispositivos Bloqueados"
        state: >
          {{ states | selectattr('entity_id', 'in', integration_entities('limitador_consumo')) | list | count }}
        attributes:
          dispositivos: >
            {# Esto requeriría acceso a hass.data, no disponible en templates #}
            {# Mejor usar los eventos #}
```

## Eventos disponibles

### `limitador_consumo_switch_off`
Disparado cuando se apaga un switch
- `switch`: entity_id del switch
- `razon`: motivo del apagado
- `potencia_actual`: potencia al momento del apagado
- `potencia_max`: límite configurado

### `limitador_consumo_switch_on`
Disparado cuando se enciende un switch
- `switch`: entity_id del switch
- `razon`: motivo del encendido
- `potencia_actual`: potencia al momento del encendido
- `potencia_max`: límite configurado

### `limitador_consumo_climate_off`
Disparado cuando se apaga un climate

### `limitador_consumo_climate_on`
Disparado cuando se enciende un climate

### `limitador_consumo_bloqueo_changed`
Disparado cuando cambia el estado de bloqueo
- `entity_id`: dispositivo afectado
- `bloqueado`: true/false
