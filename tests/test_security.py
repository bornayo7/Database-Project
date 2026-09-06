from InterfaceDatabase import create_app
from conftest import login


def test_password_and_signing_key_rotation_invalidate_sessions(config):
    from werkzeug.security import generate_password_hash
    original = create_app(config)
    client = original.test_client()
    login(client)
    cookie = client.get_cookie('session').value
    for changed in (
        {**config, 'SECRET_KEY': 'another-test-only-secret-' * 4},
        {**config, 'ADMIN_PASSWORD_HASH': generate_password_hash('changed', method='pbkdf2:sha256:1000')},
    ):
        new_client = create_app(changed).test_client()
        new_client.set_cookie('session', cookie)
        assert new_client.get('/customers').status_code == 302
        assert new_client.post('/customers/delete/1').status_code == 401
