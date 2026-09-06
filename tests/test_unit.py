from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
import hashlib

from flask import render_template
import mysql.connector
import pytest

import db
from InterfaceDatabase import ENTITIES, create_app
from validation import ValidationError, money, values_for
from conftest import login, post

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('path', ['/', '/customers','/vehicles','/employees','/dealerships','/sales','/services','/appointments','/supporting-schema','/er-diagram-image'])
def test_auth_required(app, monkeypatch, path):
    monkeypatch.setattr(db, 'connect', MagicMock(side_effect=AssertionError('Unauthorized database access')))
    assert app.test_client().get(path).status_code == 302


def test_configuration_is_fail_closed(config):
    for field in ('SECRET_KEY','ADMIN_USERNAME','ADMIN_PASSWORD_HASH'):
        with pytest.raises(RuntimeError):
            create_app({**config, field:None})
    with pytest.raises(RuntimeError):
        create_app({**config, 'ADMIN_PASSWORD_HASH':'plaintext-password'})


def test_login_logout_and_password_rotation(app, config):
    client = app.test_client()
    assert client.post('/login', data={'username':'admin','password':'test-password'}).status_code == 400
    login(client)
    with client.session_transaction() as s:
        old_csrf = s['_csrf']
    assert post(client, '/logout').status_code == 303
    assert client.get('/customers').status_code == 302
    assert client.post('/customers/add', data={'_csrf':old_csrf}).status_code == 401


def test_wrong_login_and_unicode_do_not_crash(app):
    client = app.test_client()
    client.get('/login')
    assert post(client, '/login', {'username':'😀','password':'bad'}).status_code == 401
    assert client.post('/login', data={'_csrf':'😀'}).status_code == 400


@pytest.mark.parametrize('entity', list(ENTITIES))
def test_forms_do_not_ask_for_primary_ids_and_have_csrf(client, entity):
    page = client.get('/' + entity + '/add')
    assert page.status_code == 200
    assert 'name="id"' not in page.text
    assert 'name="_csrf"' in page.text
    assert '<meta name="viewport"' in page.text


@pytest.mark.parametrize('path', ['/customers/delete/1','/employees/delete/1','/dealerships/delete/1','/vehicles/delete','/sales/delete/1','/services/delete/1','/appointments/delete/1'])
def test_get_head_never_delete(client, monkeypatch, path):
    monkeypatch.setattr(db, 'connect', MagicMock(side_effect=AssertionError('Unexpected database access')))
    assert client.get(path).status_code == 405
    assert client.head(path).status_code == 405
    assert client.post(path, data={'_csrf':'wrong'}).status_code == 400


def test_optional_form_fields(client):
    from html.parser import HTMLParser
    class Inputs(HTMLParser):
        def __init__(self, html):
            super().__init__()
            self.inputs = {}
            self.feed(html)
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'input':
                self.inputs[attrs.get('name')] = attrs
    for entity in ('customers','employees'):
        fields = Inputs(client.get('/' + entity + '/add').text).inputs
        assert 'required' not in fields['phone']
        if entity == 'customers':
            assert 'required' not in fields['loan']


@pytest.mark.parametrize('value', ['-1','0','NaN','Infinity','1.234','100000000','not money'])
def test_bad_money(value):
    with pytest.raises(ValidationError):
        money({'price':value}, 'price')


def test_optional_loan_and_input_contract():
    values = values_for('customers', dict(id='999', name='Test', credit='700', email='t@example.test'))
    assert values == ('Test', 700, 't@example.test', None, None)
    assert money({'price':'12.50'}, 'price') == Decimal('12.50')


@pytest.mark.parametrize('field,value', [('name',' '),('credit','299'),('credit','851'),('credit','1.2'),('email','not-email'),('phone','abc'),('loan','-2')])
def test_invalid_customer_before_sql(client, monkeypatch, field, value):
    monkeypatch.setattr(db, 'connect', MagicMock(side_effect=AssertionError('Invalid data reached database')))
    data = dict(name='Test', credit='700', email='t@example.test', phone='', loan='')
    data[field] = value
    assert post(client, '/customers/add', data).status_code == 400


def test_connection_cleanup_on_every_path(app, monkeypatch):
    connection = MagicMock()
    cur = connection.cursor.return_value
    monkeypatch.setattr(db, 'connect', lambda _:connection)
    with app.app_context():
        with db.cursor(write=True):
            pass
        connection.commit.assert_called_once()
        cur.close.assert_called_once()
        connection.close.assert_called_once()
        connection.reset_mock()
        with pytest.raises(TypeError):
            with db.cursor(write=True):
                raise TypeError('unexpected')
        connection.rollback.assert_called_once()
        cur.close.assert_called_once()
        connection.close.assert_called_once()
        connection.reset_mock()
        connection.cursor.side_effect = mysql.connector.Error(errno=2003)
        with pytest.raises(mysql.connector.Error):
            with db.cursor():
                pass
        connection.close.assert_called_once()


def test_database_failure_is_sanitized(app, client, monkeypatch):
    monkeypatch.setattr(db, 'connect', MagicMock(side_effect=mysql.connector.Error('PRIVATE DATA', errno=2003)))
    page = client.get('/customers')
    assert page.status_code == 503
    assert 'PRIVATE DATA' not in page.text
    assert page.headers['Cache-Control'] == 'no-store'


def test_nullable_template_and_html_escaping(app):
    customer = dict(CustomerID=1, CustomerName='<script>alert(1)</script>', CreditScore=None, Email=None, PhoneNumber=None, Loan=None)
    with app.test_request_context():
        page = render_template('customers.html', customers=[customer], mode='view', pagination=dict(previous=None,next=None,page=1,pages=1,total=1))
    assert 'Not recorded' in page
    assert '&lt;script&gt;' in page
    assert '<script>alert(1)</script>' not in page


def test_no_hardcoded_secret_and_no_manual_id_generation():
    source = (ROOT / 'InterfaceDatabase.py').read_text()
    assert 'MAX(' not in source
    assert 'next_id' not in source
    assert 'app.secret_key =' not in source


def test_all_fixture_sales_match_inventory():
    import csv
    with (ROOT / 'car.csv').open() as f:
        cars = {r['VIN']:r for r in csv.DictReader(f)}
    with (ROOT / 'transactions.csv').open() as f:
        sales = list(csv.DictReader(f))
    assert len({r['VIN #'] for r in sales}) == len(sales)
    assert all(cars[r['VIN #']]['InventoryStatus']=='Sold' for r in sales)
