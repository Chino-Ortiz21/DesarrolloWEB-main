# Aplicación Web de Comparación de Precios de Supermercados

Este proyecto es una aplicación web desarrollada con Flask y SQLAlchemy que permite a los usuarios registrarse, iniciar sesión y comparar productos de diferentes supermercados. Los productos se cargan desde archivos JSON y la autenticación de usuarios es segura.

## Requisitos

- Python 3.10 o superior
- SQL Server (puedes usar una instancia local o remota)
- Las dependencias listadas en `requirements.txt`

## Instalación

1. **Clona el repositorio o descarga el código fuente.**

2. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configura la base de datos:**
   - Edita el archivo `db_config.py` con los datos de tu servidor SQL Server.
   - Asegúrate de tener el driver ODBC adecuado instalado en tu sistema.
   - Dentro de SQL Server, asegurate de tener la tabla de usuarios, de lo contrario creala
     con el siguiente script: 

   -- Create the database
   CREATE DATABASE intetoweb;
   GO

   -- Use the newly created database
   USE intetoweb;
   GO

   -- Create the dbo.usuarios table
   CREATE TABLE dbo.usuarios (
      id_usuario INT PRIMARY KEY NOT NULL,
      nombre VARCHAR(100) NOT NULL,
      email VARCHAR(100) NOT NULL UNIQUE,
      celular VARCHAR(20) NOT NULL,
      contrasena VARCHAR(255) NOT NULL,
      fecha_registro DATETIME DEFAULT GETDATE()
   );
   GO

4. **Configura la clave secreta (opcional pero recomendado):**
   - Puedes definir la variable de entorno `FLASK_SECRET_KEY` para mayor seguridad.
   - Ejemplo en Windows:
     ```powershell
     $env:FLASK_SECRET_KEY="una_clave_secreta_segura"
     ```

5. **Actualiza los Scraping:**
   - Ejecuta los archivos "Scraping(supermrcado).py
   - Siga las instrucciones dentro de la terminal
   - Una vez finalizado los scraping, se crearan archivos (supermercado)ofertas.json
     Este archivo debe ser copiado y pegado dentro de static\data, se le debe modificar
     el nombre por: productos_(supermercado).json


6. **Ejecuta la aplicación:**
   ```bash
   flask run
   ```
   O bien:
   ```bash
   python app.py
   ```

7. **Accede a la aplicación:**
   - Abre tu navegador y ve a [http://localhost:5000](http://localhost:5000)


## Estructura del Proyecto

```
DesarrolloWEB/
│
├── app.py
├── db_config.py
├── requirements.txt
├── static/
│   └── data/
│       ├── productos_lider.json
│       ├── productos_jumbo.json
│       └── ...otros archivos de productos
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   └── ...otras plantillas
```

## Funcionalidades

- Registro y autenticación de usuarios con validaciones.
- Hash seguro de contraseñas.
- Visualización de productos por supermercado.
- Página de ofertas.
- Página de cuenta de usuario protegida.
- Manejo de sesiones.

## Notas

- Si agregas o modificas dependencias, recuerda actualizar `requirements.txt` usando:
  ```bash
  pip freeze > requirements.txt
  ```
- Si usas archivos JSON para productos, colócalos en `static/data/`.

## Licencia

Este proyecto es solo para fines educativos y personales.

@felipeMisa 
@jorgeOrtiz
© 2025 Descuentos Bear. Todos los derechos reservados.
