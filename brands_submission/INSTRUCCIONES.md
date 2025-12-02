# Cómo añadir el logo a Home Assistant Brands

## Archivos preparados

En la carpeta `custom_integrations/limitador_consumo/` están los iconos listos:
- `icon.png` (256x256 píxeles)
- `icon@2x.png` (512x512 píxeles)

## Pasos para subir a Home Assistant Brands

### 1. Hacer fork del repositorio oficial
- Ve a: https://github.com/home-assistant/brands
- Haz clic en **"Fork"** (arriba a la derecha)

### 2. Clonar tu fork
```powershell
cd C:\Users\DevCheny\Documents
git clone https://github.com/devcheny/brands.git
cd brands
```

### 3. Copiar los archivos
```powershell
# Crear la carpeta para tu integración
New-Item -ItemType Directory -Force -Path "custom_integrations\limitador_consumo"

# Copiar los iconos desde la carpeta brands_submission
Copy-Item "C:\Users\DevCheny\Documents\Home Assistant\custom_components\limitador_consumo\brands_submission\custom_integrations\limitador_consumo\*" "custom_integrations\limitador_consumo\"
```

### 4. Hacer commit y push
```powershell
git add custom_integrations/limitador_consumo/
git commit -m "Add limitador_consumo custom integration icons"
git push
```

### 5. Crear Pull Request
- Ve a tu fork en GitHub: https://github.com/devcheny/brands
- Haz clic en **"Contribute"** → **"Open pull request"**
- Título: `Add limitador_consumo custom integration`
- Descripción:
  ```
  Adding icons for the limitador_consumo custom integration.
  
  Repository: https://github.com/devcheny/limitador_consumo
  Domain: limitador_consumo
  ```
- Haz clic en **"Create pull request"**

### 6. Esperar aprobación
El equipo de Home Assistant revisará tu PR. Una vez aprobado y fusionado, tu logo estará disponible en:
- https://brands.home-assistant.io/_/limitador_consumo/icon.png
- https://brands.home-assistant.io/_/limitador_consumo/icon@2x.png

### 7. Actualizar tu integración (opcional)
Una vez que el logo esté disponible en brands.home-assistant.io, tu integración lo usará automáticamente en Home Assistant sin necesidad de cambios adicionales.

## Notas importantes

- El dominio del directorio (`limitador_consumo`) debe coincidir exactamente con el dominio en tu `manifest.json`
- Los iconos deben ser PNG con fondo transparente
- El proceso de revisión puede tomar varios días
- Una vez aprobado, el logo aparecerá automáticamente en Home Assistant y HACS
