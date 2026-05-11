# Cookiexpend API

Sistema de control y supervisión de inventarios en entornos distribuidos

![Django](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-A30000?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Poetry](https://img.shields.io/badge/Poetry-60A5FA?logo=poetry&logoColor=white)

## Inicio rápido

Realiza una instalación rápida del proyecto y ejecuta en modo desarrollo.

1. Clonar repositorio
   ```sh
   git clone https://github.com/Hyromy/Cookiexpend-API.git    # https
   git clone git@github.com:Hyromy/Cookiexpend-API.git        # ssh

   cd Cookiexpend-API
   ```

2. Instalar dependencias
   ```sh
   poetry install
   poetry shell
   ```

3. Aplicar migraciones
   ```sh
   python manage.py migrate
   ```

4. Ejecutar servidor
   ```sh
   python manage.py runserver
   ```

5. Verificar disponibilidad
   ```sh
   curl http://localhost:8000/api/health/

   # la respuesta debe ser -> {"healthy":true}
   ```

Para más detalles sobre su desarrollo y mantenimiento consulte el [manual de desarrollador](./docs/onboarding.md).

## Variables de entorno y configuración

Configura los parámetros principales de la aplicación (modo producción, base de datos, Redis, seguridad, etc.) mediante variables de entorno.

Copia el archivo `.env.example` y pegalo en la raíz del proyecto con el nombre de `.env`, configura las variables según tus necesidades.

Para más detalles sobre la configuración consulte el [manual de configuración](./docs/virtual-env.md).

## Despliegue (Docker)

Ejecuta la aplicación y sus dependencias en contenedores usando Docker.

A modo de ejemplo se incluye un [docker-compose.yml](./docker-compose.yml) configurado para un entorno pre-producción.

> [!WARNING]
> La configuración empleada no es segura para entornos de producción reales. Revisa y ajusta los valores antes de desplegar en producción.

Para más detalles sobre el despliegue consulte el [manual de operaciones](./docs/runbook.md).
