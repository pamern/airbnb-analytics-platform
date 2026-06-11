# Local PostgreSQL dbt Workflow

Tai lieu nay mo ta workflow local don gian de test data warehouse 3 layer Bronze, Silver, Gold bang Docker, PostgreSQL, pgAdmin va dbt. Production van dung MotherDuck qua profile `production`.

## 1. Services

`docker-compose.yml` co cac service:

- `postgres`: database local de dbt build/test model.
- `pgadmin`: web UI de inspect schema, table va query du lieu.
- `dbt`: container chay dbt command.
- `minio`: object storage local hien co cua project.

Volume mount:

- `./warehouse/postgres:/var/lib/postgresql/data`: giu data PostgreSQL local.
- `./warehouse/pgadmin:/var/lib/pgadmin`: giu cau hinh pgAdmin local.
- `./:/workspace`: mount source code vao dbt container.

PostgreSQL dung `PGDATA=/var/lib/postgresql/data/pgdata` de data cluster nam trong subfolder `pgdata`. Cach nay tranh loi init khi thu muc mount co file `.gitkeep`.

## 2. Start local stack

Copy file moi truong mau neu chua co `.env`:

```powershell
Copy-Item .env.example .env
```

Build va run Docker Compose:

```powershell
docker compose up -d --build
docker compose ps
```

Kiem tra dbt ket noi PostgreSQL:

```powershell
docker compose exec dbt dbt --version
docker compose exec dbt dbt debug --target local
```

## 3. pgAdmin

Mo pgAdmin:

```text
http://localhost:5050
```

Dang nhap mac dinh theo `.env.example`:

```text
Email: admin@local.dev
Password: admin
```

Tao server connection:

- Host name/address: `postgres`
- Port: `5432`
- Maintenance database: `airbnb_analytics`
- Username: `airbnb`
- Password: `airbnb`

Trong pgAdmin, inspect table tai:

```text
Servers -> airbnb local -> Databases -> airbnb_analytics -> Schemas
```

## 4. dbt profile local

`dbt/profiles.yml` dung target local PostgreSQL:

```yaml
airbnb_analytics_platform:
  target: "{{ env_var('DBT_TARGET', 'local') }}"
  outputs:
    local:
      type: postgres
      host: "{{ env_var('POSTGRES_HOST', 'localhost') }}"
      port: "{{ env_var('POSTGRES_PORT', 5432) | int }}"
      user: "{{ env_var('POSTGRES_USER', 'airbnb') }}"
      password: "{{ env_var('POSTGRES_PASSWORD', 'airbnb') }}"
      dbname: "{{ env_var('POSTGRES_DB', 'airbnb_analytics') }}"
      schema: "{{ env_var('DBT_TARGET_SCHEMA', 'public') }}"
      threads: 4
```

Production target MotherDuck:

```yaml
production:
  type: duckdb
  path: "md:{{ env_var('MOTHERDUCK_DATABASE', 'airbnb_analytics') }}?motherduck_token={{ env_var('MOTHERDUCK_TOKEN') }}"
  schema: "{{ env_var('DBT_TARGET_SCHEMA', 'main') }}"
  threads: 4
```

## 5. Seed sample data cho Bronze

Dat file CSV sample vao `dbt/seeds/`, vi du:

```text
dbt/seeds/bronze_listings.csv
dbt/seeds/bronze_calendar.csv
dbt/seeds/bronze_reviews.csv
dbt/seeds/bronze_neighbourhoods.csv
```

Chay seed tat ca:

```powershell
docker compose exec dbt dbt seed --target local
```

Chay seed mot file:

```powershell
docker compose exec dbt dbt seed --target local --select bronze_listings
```

Neu Bronze duoc load bang ingestion script thay vi seed, hay chay ingestion truoc, sau do dung pgAdmin de kiem tra bang source.

## 6. Run dbt theo layer

Chay tung layer theo thu tu:

```powershell
docker compose exec dbt dbt run --target local --select path:models/bronze
docker compose exec dbt dbt run --target local --select path:models/silver
docker compose exec dbt dbt run --target local --select path:models/gold
```

Chay mot model cu the:

```powershell
docker compose exec dbt dbt run --target local --select silver_calendar
```

Chay model kem upstream hoac downstream:

```powershell
docker compose exec dbt dbt run --target local --select +silver_calendar
docker compose exec dbt dbt run --target local --select silver_calendar+
```

Build layer kem test:

```powershell
docker compose exec dbt dbt build --target local --select path:models/silver
```

## 7. dbt test

Chay tat ca test:

```powershell
docker compose exec dbt dbt test --target local
```

Chay test theo layer:

```powershell
docker compose exec dbt dbt test --target local --select path:models/silver
```

Chay test theo model:

```powershell
docker compose exec dbt dbt test --target local --select silver_calendar
```

Test nen nam trong `schema.yml`, gom `not_null`, `unique`, `accepted_values`, `relationships` va custom assertion khi can.

## 8. dbt docs

Generate docs:

```powershell
docker compose exec dbt dbt docs generate --target local
```

Serve docs:

```powershell
docker compose run --rm -p 8080:8080 dbt dbt docs serve --target local --host 0.0.0.0 --port 8080
```

Mo docs:

```text
http://localhost:8080
```

Docs giup visualize DAG, lineage, schema va tests.

## 9. Deploy len MotherDuck

Sau khi local PostgreSQL pass seed/run/test/docs, deploy bang profile `production`.

PowerShell:

```powershell
$env:MOTHERDUCK_TOKEN="your_token_here"
$env:MOTHERDUCK_DATABASE="airbnb_analytics"
$env:DBT_TARGET_SCHEMA="main"
```

Kiem tra connection:

```powershell
docker compose run --rm -e MOTHERDUCK_TOKEN -e MOTHERDUCK_DATABASE -e DBT_TARGET_SCHEMA dbt dbt debug --target production
```

Build production theo layer:

```powershell
docker compose run --rm -e MOTHERDUCK_TOKEN -e MOTHERDUCK_DATABASE -e DBT_TARGET_SCHEMA dbt dbt build --target production --select path:models/bronze
docker compose run --rm -e MOTHERDUCK_TOKEN -e MOTHERDUCK_DATABASE -e DBT_TARGET_SCHEMA dbt dbt build --target production --select path:models/silver
docker compose run --rm -e MOTHERDUCK_TOKEN -e MOTHERDUCK_DATABASE -e DBT_TARGET_SCHEMA dbt dbt build --target production --select path:models/gold
```

Hoac build toan bo:

```powershell
docker compose run --rm -e MOTHERDUCK_TOKEN -e MOTHERDUCK_DATABASE -e DBT_TARGET_SCHEMA dbt dbt build --target production
```

## 10. Luong lam viec de xuat

```powershell
docker compose up -d --build
docker compose exec dbt dbt debug --target local
docker compose exec dbt dbt seed --target local
docker compose exec dbt dbt run --target local --select path:models/bronze
docker compose exec dbt dbt run --target local --select path:models/silver
docker compose exec dbt dbt run --target local --select path:models/gold
docker compose exec dbt dbt test --target local
docker compose exec dbt dbt docs generate --target local
```

Luu y: PostgreSQL va MotherDuck/DuckDB khac SQL dialect. Neu model dung function rieng cua DuckDB, local PostgreSQL se bao loi de team phat hien va chuan hoa SQL truoc khi deploy.
