# Limitador de Consumo

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Integración personalizada para Home Assistant que gestiona automáticamente el consumo eléctrico, apagando y reactivando dispositivos según los límites de potencia configurados.

## Características

- 🔌 **Control automático de switches**: Apaga y reactiva switches según el consumo
- 🌡️ **Soporte para climates**: Gestiona aires acondicionados y calefacción
- 📊 **Monitoreo de potencia**: Usa sensores de potencia para decisiones inteligentes
- 🔒 **Sistema de bloqueo**: Indica qué dispositivos están siendo controlados
- 🔔 **Notificaciones**: Alerta cuando se apagan o reactivan dispositivos
- ⚙️ **Configuración flexible**: Intervalos personalizables, orden de activación, etc.
- 📝 **Registro en logbook**: Historial completo de acciones

## Instalación

### Vía HACS (Recomendado)

1. Abre HACS en tu Home Assistant
2. Ve a "Integraciones"
3. Haz clic en los tres puntos (⋮) en la esquina superior derecha
4. Selecciona "Repositorios personalizados"
5. Agrega la URL: `https://github.com/devcheny/limitador_consumo`
6. Categoría: "Integration"
7. Busca "Limitador de Consumo" e instala
8. Reinicia Home Assistant

### Manual

1. Descarga la carpeta `custom_components/limitador_consumo`
2. Cópiala en tu directorio `<config>/custom_components/`
3. Reinicia Home Assistant

## Configuración

1. Ve a **Configuración** → **Dispositivos y servicios**
2. Haz clic en **Agregar integración**
3. Busca "Limitador de Consumo"
4. Completa el formulario:
   - **Potencia máxima**: Límite en vatios (W)
   - **Sensor de potencia**: Sensor que mide el consumo total
   - **Switches limitados**: Dispositivos a controlar
   - **Intervalo de desactivación**: Frecuencia de comprobación para apagar (segundos)
   - **Intervalo de activación**: Frecuencia de comprobación para reactivar (segundos)
   - **Sensores de potencia de climates**: Mapeo opcional de climates a sus sensores

## Uso

### Entidades creadas

Por cada dispositivo configurado, se crea una entidad de tipo:
```
limitador_consumo.limitador_bloqueo_[dispositivo]
```

Estados posibles:
- `off`: Dispositivo no bloqueado (control manual permitido)
- `on`: Switch bloqueado
- `heat`, `cool`, etc.: Climate bloqueado (muestra el modo HVAC anterior)

### Eventos

La integración dispara eventos que puedes usar en automatizaciones:

#### Switches
- `limitador_consumo_switch_off`: Cuando se apaga un switch
- `limitador_consumo_switch_on`: Cuando se reactiva un switch

#### Climates
- `limitador_consumo_climate_off`: Cuando se apaga un climate
- `limitador_consumo_climate_on`: Cuando se reactiva un climate

#### Bloqueos
- `limitador_consumo_bloqueo_changed`: Cuando cambia el estado de bloqueo

### Ejemplo de automatización

```yaml
automation:
  - alias: "Notificar cuando se apague un dispositivo"
    trigger:
      - platform: event
        event_type: limitador_consumo_switch_off
    action:
      - service: notify.mobile_app
        data:
          message: >
            El dispositivo {{ trigger.event.data.switch }} fue apagado.
            Potencia: {{ trigger.event.data.potencia_actual }}W / {{ trigger.event.data.potencia_max }}W
```

## Opciones avanzadas

### Invertir orden de activación
Por defecto, los dispositivos se reactivan en orden inverso al que fueron apagados.

### Notificaciones
Puedes desactivar las notificaciones persistentes en las opciones de la integración.

### Sensores de potencia de climates
Asigna sensores específicos a cada climate para un control más preciso:
```
climate.salon -> sensor.salon_potencia
```

## Actualización

### Vía HACS
HACS detectará automáticamente nuevas versiones. Haz clic en "Actualizar" cuando esté disponible.

### Manual
1. Descarga la nueva versión
2. Reemplaza la carpeta existente
3. Reinicia Home Assistant

## Solución de problemas

### Los dispositivos no se apagan
- Verifica que el sensor de potencia esté funcionando
- Comprueba los logs: `Configuración → Registros → Buscar "limitador_consumo"`
- Asegúrate de que los intervalos de comprobación sean apropiados

### Los dispositivos no se reactivan
- Verifica que el bloqueo esté activo (`limitador_consumo.limitador_bloqueo_*`)
- Comprueba que hay suficiente potencia disponible
- Para climates sin sensor, necesitas < 80% de la potencia máxima

### Después de reiniciar HA
La integración detecta automáticamente dispositivos con bloqueo activo y los mantiene controlados.

## Contribuir

¿Encontraste un bug o tienes una sugerencia?
1. Abre un [issue](https://github.com/devcheny/limitador_consumo/issues)
2. Describe el problema o mejora
3. Incluye logs si es posible

## Licencia

Este proyecto está bajo la licencia MIT.

## Autor

Creado por [@devcheny](https://github.com/devcheny)

## Agradecimientos

Desarrollado para la comunidad de Home Assistant 🏠
