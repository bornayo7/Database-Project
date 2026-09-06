"""Opaque identifiers must survive forms and SQL without normalization."""
import os
import pytest
from conftest import post
from test_mysql import database, seeded, query, client_for, DATA

pytestmark = pytest.mark.skipif(os.getenv('MYSQL_TEST') != '1', reason='Requires disposable MySQL')


def test_leading_space_vin_targets_only_the_selected_record(seeded):
    client = client_for(seeded)
    for vin in ('TEST', ' TEST'):
        response = post(client, '/vehicles/add', {**DATA['vehicles'], 'vin':vin})
        assert response.status_code == 303, response.text
    # The sale must select the space-prefixed key, not the other valid vehicle.
    assert post(client, '/sales/add', {**DATA['sales'], 'vin':' TEST'}).status_code == 303
    assert query(seeded, "SELECT InventoryStatus FROM Vehicle WHERE VIN='TEST'")[0]['InventoryStatus'] == 'Available'
    sale = query(seeded, 'SELECT SaleID FROM SaleTransaction WHERE VIN=%s', (' TEST',))[0]
    assert post(client, f'/sales/delete/{sale["SaleID"]}').status_code == 303
    assert post(client, '/vehicles/delete', {'vin':' TEST'}).status_code == 303
    assert not query(seeded, 'SELECT VIN FROM Vehicle WHERE VIN=%s', (' TEST',))
    assert query(seeded, "SELECT VIN FROM Vehicle WHERE VIN='TEST'")
