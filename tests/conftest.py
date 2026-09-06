import hashlib
import re

import pytest
from werkzeug.security import generate_password_hash

from InterfaceDatabase import create_app


@pytest.fixture
def config():
    return dict(TESTING=True, SECRET_KEY='test-only-' * 8, ADMIN_USERNAME='admin',
                ADMIN_PASSWORD_HASH=generate_password_hash('test-password', method='pbkdf2:sha256:1000'))


@pytest.fixture
def app(config):
    return create_app(config)


def login(client):
    page = client.get('/login')
    token = re.search(r'name="_csrf" value="([^"]+)"', page.text)[1]
    response = client.post('/login', data={'username':'admin','password':'test-password','_csrf':token})
    assert response.status_code == 303


@pytest.fixture
def client(app):
    client = app.test_client()
    login(client)
    return client


def post(client, path, data=None):
    with client.session_transaction() as session:
        token = session['_csrf']
    return client.post(path, data={**(data or {}), '_csrf':token})
