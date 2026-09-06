"""Opt-in end-to-end browser coverage using the same disposable MySQL fixtures."""
import os

import pytest

from test_mysql import database, seeded, query, DATA

pytestmark = pytest.mark.skipif(os.getenv('MYSQL_TEST') != '1', reason='Requires disposable MySQL')


def test_browser_customer_workflow(seeded):
    """Actual Chromium + HTTP + MySQL, enabled explicitly by CI or a local developer."""
    if os.getenv('RUN_BROWSER') != '1':
        pytest.skip('Set RUN_BROWSER=1 and install Playwright Chromium for browser coverage')
    from threading import Thread
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    server = make_server('127.0.0.1', 0, seeded)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/customers')
                page.wait_for_url(base + '/login')
                page.get_by_label('Username', exact=True).fill('admin')
                page.get_by_label('Password', exact=True).fill('test-password')
                page.get_by_role('button', name='Sign in', exact=True).click()
                page.wait_for_url(base + '/')
                page.goto(base + '/customers/add')
                page.get_by_label('Name', exact=True).fill('Browser cash buyer')
                page.get_by_label('Credit Score', exact=True).fill('700')
                page.get_by_label('Email', exact=True).fill('browser@example.test')
                assert page.locator('input[name="id"]').count() == 0
                assert page.locator('form').last.evaluate('(form) => form.checkValidity()')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.get_by_role('button', name='Add Customer', exact=True).click()
                page.wait_for_url(base + '/customers')
                page.reload()
                row = page.locator('tr').filter(has_text='Browser cash buyer')
                assert row.count() == 1
                assert 'Not recorded' in row.inner_text()
                page.on('dialog', lambda dialog: dialog.accept())
                row.get_by_role('button', name='Delete', exact=True).click()
                page.wait_for_url(base + '/customers')
                page.reload()
                assert page.locator('tr').filter(has_text='Browser cash buyer').count() == 0
                assert not query(seeded, 'SELECT CustomerID FROM Customer WHERE CustomerName=%s', ('Browser cash buyer',))
                for entity in DATA:
                    assert page.goto(base + '/' + entity + '/add').status == 200
                assert page.goto(base + '/vehicles?mode=view').status == 200
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.get_by_role('button', name='Sign out', exact=True).click()
                page.wait_for_url(base + '/login')
                page.goto(base + '/customers')
                page.wait_for_url(base + '/login')
                assert not errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
