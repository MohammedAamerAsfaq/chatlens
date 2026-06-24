# Control DB Env and Media Isolation

## Purpose

This project can now be configured so one codebase supports:

- multiple control databases
- multiple tenant databases under each control database
- segregated user uploads by control installation and tenant

## Configuration Model

The runtime reads deployment-specific values from an env file whose path is provided by:

- `CELLUSENSE_ENV_FILE`

If `CELLUSENSE_ENV_FILE` is not defined, Django falls back to:

- `.env.local_dev` in the project root, if that file exists
- otherwise the legacy in-code defaults remain active

## Required Env Keys

Use `.env.example` as the template.

Main keys:

- `APP_ENV`
- `APP_ENV_LABEL`
- `CONTROL_CODE`
- `SECRET_KEY`
- `DEBUG`
- `CONTROL_DB_NAME`
- `CONTROL_DB_USER`
- `CONTROL_DB_PASSWORD`
- `CONTROL_DB_HOST`
- `CONTROL_DB_PORT`
- `CONTROL_DB_OPTIONS_JSON`
- `ERP_PRIMARY_HOST`
- `PUBLIC_BRAND_NAME`
- `PUBLIC_WEBSITE_DOMAIN`
- `MEDIA_ROOT_BASE`

## IIS / WSGI

Each IIS site should point to its own env file through `web.config`.

Example:

```xml
<appSettings>
  <add key="WSGI_HANDLER" value="core.wsgi.application" />
  <add key="PYTHONPATH" value="C:\inetpub\wwwroot\cellusense_2" />
  <add key="CELLUSENSE_ENV_FILE" value="C:\inetpub\env\cellusense.env" />
</appSettings>
```

Examples:

- `cellusense` site -> `C:\inetpub\env\cellusense.env`
- `kiwibooks` site -> `C:\inetpub\env\kiwibooks.env`
- local development -> `.env.local_dev`

## Media Isolation

### Control-level isolation

`MEDIA_ROOT` is now derived as:

- `MEDIA_ROOT_BASE/<CONTROL_CODE>`

Example:

- `C:\cellusense_media\cellusense`
- `C:\cellusense_media\kiwibooks`
- `C:\dev_media\local_dev`

If `MEDIA_ROOT_BASE` is not configured, the app falls back to the legacy path:

- `<repo>/userupload/`

### Tenant-level isolation

Upload models now use `companycontrol.storage_paths.TenantUploadTo`.

Generated paths are:

- `<company_code>/<folder>/<filename>`

Examples:

- `plt/product_pictures/phone.jpg`
- `customer1/documents/agreement.pdf`
- `school1/business/logo/logo.png`

If no tenant context is active, files fall back under:

- `control/<folder>/<filename>`

This covers uploads done on control-host pages.

## Updated Upload Models

Tenant-aware upload paths were applied to:

- `business.Profile.logo`
- `business.Profile.logo_white`
- `business.Profile.favicon`
- `contact.ContactPicture.picture`
- `customer.CustomerPicture.picture`
- `filecenter.DocumentFileInfo.file`
- `inventory.Picture.image`

## Migration Workflow

### Control database

Run from server shell using the same env file as the IIS site:

```powershell
$env:CELLUSENSE_ENV_FILE="C:\inetpub\env\cellusense.env"
python manage.py migrate
```

Repeat per control installation.

### Tenant databases

After control migrations, run the existing tenant migration/bootstrap flow for each company under that control database.

Important:

- `python manage.py migrate` applies to the selected control DB
- it does not automatically migrate all tenant DBs

## Existing Media

This implementation changes where new uploads are stored.

Existing files already stored in legacy flat folders are not moved automatically.

Recommended rollout:

1. deploy env + media root changes
2. start storing new files in segregated folders
3. migrate old files later with a controlled script if needed

## Secret Keys

Generate keys on the server, not in git:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Put the generated value into the server env file:

```env
SECRET_KEY=generated-value-here
```

## Git Hygiene

Commit:

- `.env.example`

Do not commit:

- `.env`
- `.env.local_dev`
- `.env.cellusense`
- `.env.kiwibooks`
- any real secret-bearing env file
