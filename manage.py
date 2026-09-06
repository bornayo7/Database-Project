"""Explicit, non-destructive schema initialization and legacy/data import commands."""
import argparse
import csv
from pathlib import Path

import mysql.connector

from db import connect, identifier, settings

ROOT = Path(__file__).resolve().parent
# Order is also the foreign-key-safe import order.
MAP = (
 ('Dealership','dealerships','dealership.csv',('DealershipID','Address','City','State','ZipCode'),
  ('dealership_id','address','city','state','zip_code'),('Dealership ID','Address','City','State','Zip Code')),
 ('Customer','customers','customers.csv',('CustomerID','CustomerName','CreditScore','PhoneNumber','Email','Loan'),
  ('customer_id','name','credit_score','phone_number','email','loan'),('Customer ID','Name','Credit Score','Phone Number','Email','Loan')),
 ('Employee','employee','employee.csv',('EmployeeID','EmployeeName','PhoneNumber','Email','Position','DealershipID'),
  ('employee_id','name','phone_number','email','position','dealership_id'),('Employee ID','Name','Phone Number','Email','Position','Dealership ID')),
 ('Vehicle','car','car.csv',('VIN','Model','Type','Year','Brand','DealershipID','Miles','BoughtPrice','InventoryStatus','ListingPrice'),
  ('vin','model','type','year','brand','dealership','miles','bought_price','inventory_status','listing_price'),
  ('VIN','Model','Type','Year','Brand','Dealership','Miles','BoughtPrice','InventoryStatus','ListingPrice')),
 ('SaleTransaction','transactions','transactions.csv',('SaleID','SaleDate','CustomerID','EmployeeID','VIN','SoldPrice'),
  ('sale_id','date','customer_id','employee_id','vin','sold_price'),('Sale ID','Date','Customer ID','Employee ID','VIN #','Sold Price')),
 ('ServiceRecord','servicerecord','servicerecord.csv',('ServiceID','VIN','Cost','ServiceDate','ServiceDone','EmployeeID'),
  ('service_id','vin','cost','date','service_done','employee_id'),('Service ID','VIN #','Cost','Date','Service Done','Employee ID')),
 ('ServiceAppointment','serviceappointment','serviceappointment.csv',('AppointmentID','EmployeeID','CustomerID','VIN','Status','AppointmentDate','DealershipID'),
  ('appointment_id','employee_id',None,'vin','status','appointment_date',None),
  ('Appointment ID','Employee ID','Customer ID','VIN #','Status','Appointment Date','Dealership ID')),
)


def statements(path):
    """Project SQL contains ordinary statements only, not stored-program DELIMITER blocks."""
    sql = '\n'.join(line for line in path.read_text().splitlines() if not line.lstrip().startswith('--'))
    return [part.strip() for part in sql.split(';') if part.strip()]


def initialize(connection):
    with connection.cursor() as cur:
        cur.execute('SHOW TABLES')
        if cur.fetchall():
            raise ValueError('Refusing to initialize a nonempty database. Use a new target database for migration.')
        for statement in statements(ROOT / 'schema.sql'):
            cur.execute(statement)
    connection.commit()


def check_empty(connection):
    with connection.cursor() as cur:
        cur.execute('SELECT Version FROM SchemaVersion')
        if cur.fetchall() != [(1,)]:
            raise ValueError('Initialize the target with schema.sql version 1 first.')
        for table, *_ in MAP:
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            if cur.fetchone()[0]:
                raise ValueError('Import target must have no entity data. Existing records will not be overwritten.')
    connection.rollback()


def import_rows(connection, batches):
    """All data imports commit once. Failures leave the initialized target empty."""
    check_empty(connection)
    counts = {}
    try:
        with connection.cursor() as cur:
            for table, columns, rows in batches:
                rows = list(rows)
                if table != 'Vehicle':
                    primary_key = next(mapping[3][0] for mapping in MAP if mapping[0] == table)
                    pk_index = columns.index(primary_key)
                    for row in rows:
                        value = str(row[pk_index])
                        if not value.isascii() or not value.isdecimal() or int(value) <= 0:
                            raise ValueError(f'{table}: imported primary IDs must be positive integers; no IDs were generated or replaced.')
                if table == 'Customer':
                    # Legacy SQL's 0.00 means no loan, matching blank CSV cells.
                    index = columns.index('Loan') if 'Loan' in columns else None
                    rows = [tuple(None if i == index and str(v) in ('0','0.0','0.00') else v for i,v in enumerate(row)) for row in rows]
                if rows:
                    cur.executemany(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join(["%s"] * len(columns))})', rows)
                counts[table] = len(rows)
            # Sales are authoritative; do not discard transactions to make inventory look available.
            cur.execute("UPDATE Vehicle v JOIN SaleTransaction s ON s.VIN=v.VIN SET v.InventoryStatus='Sold' WHERE v.InventoryStatus<>'Sold'")
            counts['inventory_statuses_reconciled'] = cur.rowcount
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return counts


def csv_batches(directory):
    for table, _, filename, columns, _, headers in MAP:
        with (directory / filename).open(newline='', encoding='utf-8-sig') as source:
            reader = csv.DictReader(source)
            if not set(headers).issubset(reader.fieldnames or []) or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError(f'{filename}: missing or duplicate CSV headers.')
            rows = []
            for row in reader:
                if None in row or any(row[h] is None for h in headers):
                    raise ValueError(f'{filename}: malformed row at line {reader.line_num}.')
                rows.append(tuple(row[h].strip() or None for h in headers))
        yield table, columns, rows


def legacy_batches(source):
    """Copy snake_case legacy SQL or pre-repair CamelCase tables without inventing absent relationships."""
    with source.cursor(dictionary=True, buffered=True) as cur:
        cur.execute('SHOW TABLES')
        tables = {next(iter(row.values())).casefold(): next(iter(row.values())) for row in cur.fetchall()}
        canonical = 'vehicle' in tables
        for table, old_table, _, columns, old_columns, _ in MAP:
            requested = table if canonical else old_table
            src = tables.get(requested.casefold())
            if src is None:
                raise ValueError(f'Missing source table: {requested}')
            cur.execute(f'SHOW COLUMNS FROM {identifier(src)}')
            existing_names = {r['Field'].casefold(): r['Field'] for r in cur.fetchall()}
            existing = set(existing_names.values())
            source_cols = tuple(existing_names.get((col or '').casefold()) for col in (columns if canonical else old_columns))
            fields = [identifier(col) if col in existing else 'NULL' for col in source_cols]
            # Only known optional legacy columns may be missing. Never synthesize primary IDs or VINs.
            allowed_missing = {'ListingPrice','CustomerID','DealershipID'} if table in ('Vehicle','ServiceAppointment') else set()
            for target, src_col in zip(columns, source_cols):
                if src_col not in existing and target not in allowed_missing:
                    raise ValueError(f'Missing source column {src}.{src_col} for {target}')
            extra = ('RestockStatus',) if table == 'SaleTransaction' and 'restockstatus' in existing_names else ()
            fields += [identifier(existing_names[c.casefold()]) for c in extra]
            # Read positionally so multiple missing legacy columns remain distinct NULL values.
            with source.cursor() as positional:
                positional.execute(f'SELECT {",".join(fields)} FROM {identifier(src)}')
                rows = positional.fetchall()
            yield table, columns + extra, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init-db','import-demo','migrate-legacy'))
    parser.add_argument('--source', help='Existing source schema for migrate-legacy. DB_NAME is the initialized empty target.')
    args = parser.parse_args()
    config = settings()
    target = connect(config)
    try:
        if args.command == 'init-db':
            initialize(target)
            print('Initialized schema version 1. No data was imported.')
        elif args.command == 'import-demo':
            print(import_rows(target, csv_batches(ROOT)))
        else:
            if not args.source or args.source == config['DB_NAME']:
                raise ValueError('Provide --source and use a different, empty DB_NAME target. The source is never modified.')
            identifier(args.source)
            source = connect({**config, 'DB_NAME': args.source})
            try:
                source.start_transaction(consistent_snapshot=True, readonly=True)
                print(import_rows(target, legacy_batches(source)))
            finally:
                source.rollback()
                source.close()
    finally:
        target.close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, mysql.connector.Error) as error:
        # MySQL messages can include input values. Print a diagnostic number, not raw data.
        message = f'Database operation failed (errno={error.errno}). Check schema/constraints; target data was not partially imported.' if isinstance(error, mysql.connector.Error) else str(error)
        raise SystemExit(message)
