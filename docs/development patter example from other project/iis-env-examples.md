# IIS Env Examples

## Purpose

These examples show how to run one codebase against multiple control databases with IIS + WSGI while also segregating media by:

- control installation
- tenant company code

## Env Files

Use these repo templates as the starting point:

- `.env.cellusense.example`
- `.env.kiwibooks.example`
- `.env.local_dev.example`

For control-host branding:

- `APP_ENV` should stay machine-friendly, for example `cellusense`
- `APP_ENV_LABEL` should be human-friendly, for example `Cellusense ERP Host`

Copy them outside the repo and rename them to real env files, for example:

- `C:\inetpub\env\cellusense.env`
- `C:\inetpub\env\kiwibooks.env`
- `C:\projects\cellusense_2\.env.local_dev`

Do not commit the real env files.

## Example IIS web.config

### Cellusense site

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <appSettings>
    <add key="WSGI_HANDLER" value="core.wsgi.application" />
    <add key="PYTHONPATH" value="C:\inetpub\wwwroot\cellusense_2" />
    <add key="CELLUSENSE_ENV_FILE" value="C:\inetpub\env\cellusense.env" />
  </appSettings>
  <system.webServer>
    <handlers>
      <add name="Python FastCGI"
           path="*"
           verb="*"
           modules="FastCgiModule"
           scriptProcessor="C:\Python310\python.exe|C:\Python310\Lib\site-packages\wfastcgi.py"
           resourceType="Unspecified"
           requireAccess="Script" />
    </handlers>
  </system.webServer>
</configuration>
```

### Kiwibooks site

Same file, but point to the Kiwibooks env:

```xml
<add key="CELLUSENSE_ENV_FILE" value="C:\inetpub\env\kiwibooks.env" />
```

## Media Layout

With:

- `MEDIA_ROOT_BASE=C:\cellusense_media`
- `CONTROL_CODE=cellusense`

effective media root becomes:

- `C:\cellusense_media\cellusense`

New uploads then go under:

- `C:\cellusense_media\cellusense\<company_code>\...`

Examples:

- `C:\cellusense_media\cellusense\plt\product_pictures\phone.jpg`
- `C:\cellusense_media\kiwibooks\school1\documents\invoice.pdf`
- `C:\dev_media\local_dev\customer1\customer_pictures\photo.png`

## IIS Media Mapping

If IIS serves `/media/`, map the physical path to the control-specific media root for that site.

Examples:

- Cellusense site `/media/` -> `C:\cellusense_media\cellusense`
- Kiwibooks site `/media/` -> `C:\cellusense_media\kiwibooks`

This keeps control installations isolated even if they share the same code folder.

## Secret Key Generation

Generate on the server:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Put the result into the env file:

```env
SECRET_KEY=generated-value-here
```

## Optional Draft Autosave Settings

These map directly to `core/settings.py` and control voucher draft autosave globally for the currently wired add forms:

- Bill
- Invoice
- Purchase Order v1
- Sales Order v1
- Sales Return

```env
DRAFT_AUTOSAVE_ENABLED=true
DRAFT_AUTOSAVE_DEBOUNCE_SECONDS=4
DRAFT_AUTOSAVE_MAX_FREQUENCY_SECONDS=30
```

Notes:

- set `DRAFT_AUTOSAVE_ENABLED=false` to hard-disable all wired voucher draft autosave flows without code changes
- `DRAFT_AUTOSAVE_MAX_FREQUENCY_SECONDS` should be greater than or equal to the debounce setting

## Optional Cache / Redis Settings

These map directly to `core/settings.py` and control whether the new tenant-aware cache layer uses local memory only or Redis.

```env
CACHE_ENABLED=false
CACHE_DEFAULT_TIMEOUT=300
CACHE_KEY_PREFIX=cellusense:cellusense
REDIS_URL=redis://127.0.0.1:6379
REDIS_CACHE_DB=10
```

Notes:

- `CACHE_ENABLED=false` keeps caching on `LocMemCache`, which is safe for local testing and single-process fallback
- `CACHE_ENABLED=true` switches Django's `default` cache to Redis
- `REDIS_URL` should normally point to the Redis server only; the cache DB index is supplied separately by `REDIS_CACHE_DB`
- `CACHE_KEY_PREFIX` should stay unique per control host so multiple deployments do not share cache keys accidentally
- these env values are still the bootstrap / fallback source even though cache settings can now also be saved from the UI

## Cache Management UI

Cache operations are now available from:

- `/setting/cache_management`

The page supports:

- viewing the current active backend and mode
- seeing whether runtime config is coming from env or database
- saving DB-backed cache settings for the next restart
- clearing application cache
- running `Test Connection` against the current Redis form values without saving them

Scope rules:

- Cache Management is control-DB only
- it is hidden from tenant shortcut context
- direct tenant access is blocked
- tenants inherit the cache backend selected for the control host / running site
- tenant isolation is handled by tenant-aware cache keys rather than separate tenant cache configuration rows

Important behavior:

- saved cache settings do not hot-apply to the current process
- recycle IIS or restart the app after saving
- `Reset To Env Default On Restart` removes the DB override and returns runtime control to env values

Credential note:

- enter the raw Redis password in the UI
- do not include shell quotes in the password field
- if shell testing is needed, the shell command may still require quotes around the password even though the UI field does not

## Migration Commands

### Cellusense control DB

```powershell
cd C:\inetpub\wwwroot\cellusense_2
$env:CELLUSENSE_ENV_FILE="C:\inetpub\env\cellusense.env"
python manage.py migrate
```

Then run the existing tenant migration/bootstrap flow for companies inside the Cellusense control DB.

### Kiwibooks control DB

```powershell
cd C:\inetpub\wwwroot\cellusense_2
$env:CELLUSENSE_ENV_FILE="C:\inetpub\env\kiwibooks.env"
python manage.py migrate
```

Then run the existing tenant migration/bootstrap flow for companies inside the Kiwibooks control DB.

### Local development

```powershell
cd C:\Users\Administrator\OneDrive - Perfect Link Technologies\Documents\Visual Studio Code\Python\cellusense_2
$env:CELLUSENSE_ENV_FILE="C:\Users\Administrator\OneDrive - Perfect Link Technologies\Documents\Visual Studio Code\Python\cellusense_2\.env.local_dev"
python manage.py migrate
```

## Deployment Order

1. Create the real env file from the correct example.
2. Point IIS `web.config` to that env file.
3. Ensure the external media root exists.
4. Map `/media/` to the control-specific media root in IIS.
5. Run control DB migrations.
6. Run tenant DB migration/bootstrap flow.
7. Recycle the IIS app pool.
8. Validate the cache backend:

```powershell
python manage.py check_redis
```

## Notes

- `python manage.py migrate` applies to the selected control DB only.
- Tenant DBs still require the existing per-company migration/bootstrap process.
- Existing legacy uploads remain in the old location until moved separately.
