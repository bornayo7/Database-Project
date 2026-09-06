"""Integration tests use only disposable schemas and require explicit MYSQL_TEST=1."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import mysql.connector
import pytest

import db
from InterfaceDatabase import create_app, LIST_SQL
from manage import initialize, import_rows, csv_batches, legacy_batches, statements
from conftest import login, post

pytestmark = pytest.mark.skipif(os.getenv('MYSQL_TEST') != '1', reason='Requires explicit disposable MySQL test service')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database(config):
    cfg = {**db.settings(), **config, 'DB_NAME':'dealership_test_' + uuid4().hex[:12]}
    admin = mysql.connector.connect(host=cfg['DB_HOST'], port=cfg['DB_PORT'], user=cfg['DB_USER'], password=cfg['DB_PASSWORD'], use_pure=True, autocommit=True)
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE `{cfg["DB_NAME"]}` CHARACTER SET utf8mb4')
    connection = db.connect(cfg)
    initialize(connection)
    connection.close()
    app = create_app(cfg)
    try:
        yield app
    finally:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE `{cfg["DB_NAME"]}`')
        admin.close()


def query(app, sql, params=(), write=False):
    with app.app_context(), db.cursor(write=write) as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.with_rows else cur.lastrowid


@pytest.fixture
def seeded(database):
    query(database, "INSERT INTO Dealership(DealershipID,Address,City,State,ZipCode) VALUES (1,'1 Main','Dallas','TX','75001'),(2,'2 Main','Dallas','TX','75002')", write=True)
    query(database, "INSERT INTO Customer(CustomerID,CustomerName,CreditScore,Email,Loan) VALUES (1,'Customer',600,'c@example.test',NULL)", write=True)
    query(database, "INSERT INTO Employee(EmployeeID,EmployeeName,Position,DealershipID) VALUES (1,'Mechanic','Mechanic',1),(2,'Salesperson','Salesperson',1)", write=True)
    for vin, status in [('available','Available'),('reserved','Reserved'),('sold','Sold')]:
        query(database, 'INSERT INTO Vehicle(VIN,Model,Brand,DealershipID,Miles,BoughtPrice,ListingPrice,InventoryStatus) VALUES (%s,\'Model\',\'Brand\',1,NULL,1000,NULL,%s)', (vin,status), write=True)
    query(database, "INSERT INTO SaleTransaction(SaleID,SaleDate,CustomerID,EmployeeID,VIN,SoldPrice,RestockStatus) VALUES (1,'2026-01-01',1,1,'sold',1500,'Available')", write=True)
    query(database, "INSERT INTO ServiceRecord(ServiceID,VIN,Cost,ServiceDate,ServiceDone,EmployeeID) VALUES (1,'available',NULL,'2026-01-01','Brakes',1)", write=True)
    query(database, "INSERT INTO ServiceAppointment(AppointmentID,EmployeeID,CustomerID,VIN,Status,AppointmentDate,DealershipID) VALUES (1,1,NULL,'available','Scheduled','2026-01-01',NULL)", write=True)
    return database


def client_for(app):
    client = app.test_client()
    login(client)
    return client


@pytest.mark.parametrize('path', ['/', '/customers','/vehicles','/employees','/dealerships','/sales','/services','/appointments','/supporting-schema','/er-diagram-image'])
def test_read_routes_with_legacy_nulls(seeded, path):
    assert client_for(seeded).get(path).status_code == 200


def test_read_routes_empty(database):
    client = client_for(database)
    for path in ('/','/customers','/vehicles','/employees','/dealerships','/sales','/services','/appointments'):
        assert client.get(path).status_code == 200


DATA = {
 'customers':dict(id='999',name='New customer',credit='710',email='new@example.test',phone='',loan=''),
 'employees':dict(id='999',name='New employee',position='Mechanic',dealership_id='1',email='new@example.test',phone=''),
 'dealerships':dict(id='999',address='3 Main',city='Austin',state='TX',zipcode='78701'),
 'vehicles':dict(vin='new-vehicle',model='Model',type='Wagon',year='1886',brand='Brand',dealership_id='1',miles='0',bought_price='1000.01',listing_price='1500.01',status='Available'),
 'sales':dict(id='999',date='2026-02-01',customer_id='1',employee_id='2',vin='available',sold_price='1500.01'),
 'services':dict(id='999',vin='available',cost='100.25',date='2026-02-01',service_done='Brakes',employee_id='1'),
 'appointments':dict(id='999',employee_id='1',customer_id='1',vin='available',status='Scheduled',date='2026-02-01',dealership_id='1'),
}


@pytest.mark.parametrize('entity', list(DATA))
def test_all_create_routes_persist_and_ignore_manual_id(seeded, entity):
    from InterfaceDatabase import ENTITIES
    client = client_for(seeded)
    response = post(client, '/' + entity + '/add', DATA[entity])
    assert response.status_code == 303, response.text
    table, pk, *_ = ENTITIES[entity]
    if entity == 'vehicles':
        row = query(seeded, "SELECT * FROM Vehicle WHERE VIN='new-vehicle'")[0]
        assert row['ListingPrice'] == Decimal('1500.01')
    else:
        rows = query(seeded, f'SELECT {pk} FROM {table} ORDER BY {pk}')
        assert len(rows) >= 2
        assert all(r[pk] != 999 for r in rows)
    # A separate application/client uses the same persisted database after recreation.
    fresh = client_for(create_app(seeded.config))
    assert fresh.get('/' + entity).status_code == 200


@pytest.mark.parametrize('status', ['Available','Reserved'])
def test_sale_lifecycle_restores_previous_status(seeded, status):
    vin = status.lower()
    client = client_for(seeded)
    assert post(client, '/sales/add', {**DATA['sales'],'vin':vin}).status_code == 303
    assert query(seeded, 'SELECT InventoryStatus FROM Vehicle WHERE VIN=%s', (vin,))[0]['InventoryStatus']=='Sold'
    sale = query(seeded, 'SELECT SaleID,RestockStatus FROM SaleTransaction WHERE VIN=%s', (vin,))[0]
    assert sale['RestockStatus'] == status
    assert post(client, f'/sales/delete/{sale["SaleID"]}').status_code == 303
    assert query(seeded, 'SELECT InventoryStatus FROM Vehicle WHERE VIN=%s', (vin,))[0]['InventoryStatus']==status
    assert post(client, f'/sales/delete/{sale["SaleID"]}').status_code == 404


def test_legacy_sale_reversal_requires_explicit_choice(seeded):
    query(seeded, 'UPDATE SaleTransaction SET RestockStatus=NULL WHERE SaleID=1', write=True)
    client = client_for(seeded)
    assert post(client, '/sales/delete/1').status_code == 400
    assert len(query(seeded, 'SELECT * FROM SaleTransaction WHERE SaleID=1')) == 1
    assert post(client, '/sales/delete/1', {'restock_status':'Reserved'}).status_code == 303
    assert query(seeded, "SELECT InventoryStatus FROM Vehicle WHERE VIN='sold'")[0]['InventoryStatus'] == 'Reserved'


def test_concurrent_sales_only_one_wins(seeded):
    gate = Barrier(2)
    def sell():
        client = client_for(seeded)
        gate.wait(timeout=10)
        return post(client, '/sales/add', DATA['sales']).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:sell(), range(2)))
    assert sorted(results) == [303,409]
    assert len(query(seeded, "SELECT * FROM SaleTransaction WHERE VIN='available'")) == 1


def test_concurrent_customer_ids_do_not_collide(seeded):
    gate = Barrier(6)
    def add(index):
        client = client_for(seeded)
        gate.wait(timeout=10)
        return post(client, '/customers/add', {**DATA['customers'],'name':f'Concurrent {index}'}).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(add, range(6))) == [303]*6
    rows = query(seeded, "SELECT CustomerID FROM Customer WHERE CustomerName LIKE 'Concurrent %'")
    assert len(rows)==len({r['CustomerID'] for r in rows})==6


def test_sale_rollback_on_second_statement_failure(seeded, monkeypatch):
    original = db.cursor
    @contextmanager
    def failing_cursor(write=False):
        with original(write=write) as cur:
            class Fault:
                def __getattr__(self, key): return getattr(cur,key)
                def execute(self, sql, params=()):
                    if sql.startswith('UPDATE Vehicle'):
                        raise mysql.connector.DatabaseError('injected', errno=2000)
                    return cur.execute(sql, params)
            yield Fault()
    client = client_for(seeded)
    with monkeypatch.context() as patch:
        patch.setattr(db, 'cursor', failing_cursor)
        assert post(client, '/sales/add', DATA['sales']).status_code == 503
    assert not query(seeded, "SELECT * FROM SaleTransaction WHERE VIN='available'")
    assert query(seeded, "SELECT InventoryStatus FROM Vehicle WHERE VIN='available'")[0]['InventoryStatus']=='Available'


@pytest.mark.parametrize('vin', ['TEST#ALT','TEST?ALT','TEST/ALT','TEST"ALT'])
def test_delete_exact_vehicle_identifier(seeded, vin):
    client = client_for(seeded)
    for identifier in ('TEST', vin):
        assert post(client, '/vehicles/add', {**DATA['vehicles'],'vin':identifier}).status_code == 303
    assert post(client, '/vehicles/delete', {'vin':vin}).status_code == 303
    assert not query(seeded, 'SELECT VIN FROM Vehicle WHERE VIN=%s',(vin,))
    assert query(seeded, "SELECT VIN FROM Vehicle WHERE VIN='TEST'")


def test_deletion_errors_and_success(seeded):
    client = client_for(seeded)
    assert post(client, '/customers/delete/987654').status_code == 404
    assert post(client, '/customers/delete/1').status_code == 409
    for entity,path in [('appointments','/appointments/delete/1'),('services','/services/delete/1')]:
        assert post(client,path).status_code == 303
        assert post(client,path).status_code == 404
    # The remaining sale must be reversed before referenced customer/vehicle rows can be deleted.
    assert post(client, '/sales/delete/1').status_code == 303
    assert post(client, '/customers/delete/1').status_code == 303
    for vin in ('available','reserved','sold'):
        assert post(client, '/vehicles/delete', {'vin':vin}).status_code == 303
    for identifier in (1,2):
        assert post(client, f'/employees/delete/{identifier}').status_code == 303
    for identifier in (1,2):
        assert post(client, f'/dealerships/delete/{identifier}').status_code == 303


def test_stock_count_and_pagination(seeded):
    rows = query(seeded, LIST_SQL['dealerships'])
    assert [r['CarCount'] for r in rows] == [2,0]
    seeded.config['PAGE_SIZE']=1
    client = client_for(seeded)
    page = client.get('/vehicles?status=Available&mode=view')
    assert page.status_code==200
    assert '(1 records)' in page.text
    assert 'class="delete-form"' not in page.text
    assert client.get('/vehicles?status=invalid').status_code==400
    assert client.get('/vehicles?page=0').status_code==400
    assert client.get('/vehicles?page=999').status_code==404
    assert client.get('/vehicles?page=2').status_code==200


def test_reports_execute_and_customer_weighting_is_correct(seeded):
    query(seeded, "INSERT INTO Customer(CustomerID,CustomerName,CreditScore) VALUES (2,'Repeat buyer',800)", write=True)
    for index in (1,2):
        vin=f'report{index}'
        query(seeded, "INSERT INTO Vehicle(VIN,Model,InventoryStatus) VALUES (%s,'Model','Sold')", (vin,),write=True)
        query(seeded, "INSERT INTO SaleTransaction(SaleDate,CustomerID,EmployeeID,VIN,SoldPrice) VALUES ('2026-03-01',2,NULL,%s,1500)", (vin,),write=True)
    credit = never_sellers = None
    for sql in statements(ROOT/'dealership_queries.sql'):
        result = query(seeded,sql,write=sql.startswith('CREATE'))
        if 'AS avg_credit_score' in sql:
            credit=result[0]['avg_credit_score']
        if 'WHERE NOT EXISTS' in sql:
            never_sellers={r['EmployeeID'] for r in result}
    assert credit==Decimal('700')
    assert never_sellers=={2}


def test_entire_csv_import_and_duplicate_import_is_rejected(database):
    connection = db.connect(database.config)
    try:
        counts = import_rows(connection,csv_batches(ROOT))
        assert counts['Customer']==counts['Vehicle']==counts['SaleTransaction']==counts['ServiceRecord']==counts['ServiceAppointment']==2000
        assert counts['Dealership']==4 and counts['Employee']==200
        assert query(database, "SELECT COUNT(*) AS count FROM Vehicle WHERE InventoryStatus<>'Sold'")[0]['count']==0
        assert client_for(database).get('/customers').status_code==200
        with pytest.raises(ValueError):
            import_rows(connection,csv_batches(ROOT))
        with pytest.raises(ValueError):
            initialize(connection)
    finally:
        connection.close()


def test_failed_import_rolls_back_all_entity_rows(database):
    connection=db.connect(database.config)
    batches=[('Dealership',('DealershipID','Address','City','State','ZipCode'),[(1,'Address','Dallas','TX','75001')]),
             ('Customer',('CustomerID','CustomerName','CreditScore'),[(1,'Invalid',999)])]
    try:
        with pytest.raises(mysql.connector.Error):
            import_rows(connection,batches)
    finally:
        connection.close()
    assert query(database,'SELECT COUNT(*) AS count FROM Dealership')[0]['count']==0


def test_legacy_copy_preserves_source_and_missing_relationships(database):
    name = 'dealership_test_legacy_' + uuid4().hex[:8]
    admin = db.connect(database.config)
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE `{name}`')
    source = db.connect({**database.config, 'DB_NAME':name})
    target = db.connect(database.config)
    try:
        with source.cursor() as cur:
            for statement in statements(ROOT/'tests/legacy_schema.sql'):
                cur.execute(statement)
            cur.execute("INSERT INTO dealerships VALUES(1,'A','Dallas','TX','75001')")
            cur.execute("INSERT INTO customers VALUES(1,'Customer',700,NULL,NULL,0)")
            cur.execute("INSERT INTO employee VALUES(1,'Employee',NULL,NULL,'Mechanic',1)")
            cur.execute("INSERT INTO car VALUES('legacy','Model',NULL,NULL,NULL,1,NULL,NULL,'Available',NULL)")
            cur.execute("INSERT INTO transactions VALUES(1,'2026-01-01',1,1,'legacy',1000)")
            cur.execute("INSERT INTO serviceappointment VALUES(1,1,'legacy','Scheduled','2026-01-01')")
        source.commit()
        source.start_transaction(consistent_snapshot=True,readonly=True)
        counts=import_rows(target,legacy_batches(source))
        assert counts['inventory_statuses_reconciled']==1
        assert query(database,'SELECT CustomerID,DealershipID FROM ServiceAppointment')[0]==dict(CustomerID=None,DealershipID=None)
        assert query(database,'SELECT Loan FROM Customer')[0]['Loan'] is None
        source.rollback()
        with source.cursor() as cur:
            cur.execute("SELECT inventory_status FROM car WHERE vin='legacy'")
            assert cur.fetchone()[0]=='Available'
        assert client_for(database).get('/appointments').status_code==200
        assert client_for(database).get('/vehicles').status_code==200
    finally:
        source.close();target.close()
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE `{name}`')
        admin.close()
