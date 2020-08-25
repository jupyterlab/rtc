#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    create table companies (
        id serial primary key,
        name text not null
    );
    create table beverages (
        id serial primary key,
        company_id int not null references companies,
        distributor_id int references companies,
        name text not null
    );
EOSQL