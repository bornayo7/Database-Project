"""One-time, branch-only transformation of the already-reviewed original assets."""
from pathlib import Path
import re
import csv
import sys

root = Path(sys.argv[1]).resolve()
legacy = (root/'dealership_queries.sql').read_text()
legacy = legacy[:legacy.index('-- SECTION 2:')]
legacy = '\n'.join(line for line in legacy.splitlines() if not line.startswith(('CREATE DATABASE','USE ')))
(root/'tests/legacy_schema.sql').write_text(legacy)

for path in root.glob('*.html'):
    if path.name in ('login.html','error.html','pagination.html'):
        continue
    s = path.read_text()
    s = re.sub(r"url_for\('([a-z_]+)'", lambda m: "url_for('web." + m[1] + "'", s)
    s = re.sub(r'            <div class="form-group">\s*<label>[^<]* ID</label>\s*<input name="id"[^>]*>\s*</div>\n', '', s)
    if path.name.startswith('add_'):
        s = s.replace('<form method="POST">', '<form method="POST">\n        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">\n        {% if error %}<p class="flash-error" role="alert">{{ error }}</p>{% endif %}')
        def input_values(m):
            tag = m[0]
            name = re.search(r'name="([^"]+)"', tag)[1]
            if name == '_csrf': return tag
            tag = re.sub(r' value="[^"]*"', '', tag)
            if name in ('phone','loan'):
                tag = tag.replace(' required', '')
            if name == 'year':
                tag = tag.replace('max="2027"', 'max="{{ max_year }}"')
            return tag[:-1] + f' id="{name}" value="{{{{ values.get(\'{name}\', \'\') }}}}">'
        s = re.sub(r'<input name="[^"]+"[^>]*>', input_values, s)
        s = re.sub(r'<label>([^<]+)</label>(\s*)<(input|select)([^>]*name="([^"]+)"[^>]*)>',
                   lambda m: f'<label for="{m[5]}">{m[1]}</label>{m[2]}<{m[3]}{m[4]}' + (f' id="{m[5]}"' if m[3]=='select' else '') + '>', s)
        for field, choices in [('type','vehicle_types'),('position','positions'),('service_done','service_types')]:
            s = re.sub(r'(<select name="' + field + r'"[^>]*>).*?(</select>)',
                       lambda m: m[1] + f"\n                    {{% for option in {choices} %}}\n                    <option{{% if values.get('{field}') == option %}} selected{{% endif %}}>{{{{ option }}}}</option>\n                    {{% endfor %}}\n                " + m[2], s, flags=re.S)
        if 'select name="status"' in s:
            choices = 'appointment_statuses' if path.name=='add_appointment.html' else "('Available', 'Reserved')"
            s = re.sub(r'(<select name="status"[^>]*>).*?(</select>)',
                       lambda m: m[1] + f"\n                    {{% for option in {choices} %}}\n                    <option{{% if values.get('status') == option %}} selected{{% endif %}}>{{{{ option }}}}</option>\n                    {{% endfor %}}\n                " + m[2], s, flags=re.S)
        if path.name == 'add_vehicle.html':
            at = '            <div class="form-group">\n                <label for="status">Status</label>'
            new = '''            <div class="form-group">
                <label for="listing_price">Listing Price</label>
                <input name="listing_price" id="listing_price" type="number" step="0.01" min="0.01" max="99999999.99" value="{{ values.get('listing_price', '') }}" required>
            </div>
'''
            if at not in s: raise RuntimeError('Vehicle form anchor missing')
            s = s.replace(at, new + at)
        if path.name == 'add_customer.html':
            s = s.replace('Loan Amount</label>', 'Loan Amount (optional)</label>')
        s = s.replace('Employee ID (Mechanic)', 'Employee ID')
    s = re.sub(r'\$\{\{ "\{:,\.2f\}"\.format\(([^)]+)\) \}\}', r'{{ \1|money }}', s)
    s = re.sub(r'\{\{ "\{:,\}"\.format\(([^)]+)\) \}\}', r'{{ \1|number }}', s)
    s = s.replace('${{ "{:,.0f}".format(total_revenue) }}', '{{ total_revenue|money }}')
    if path.name in ('customers.html','vehicles.html','employees.html','dealerships.html','sales.html','services.html','appointments.html'):
        mapping = {'customers':('customer','c.CustomerID'), 'vehicles':('vehicle','v.VIN'), 'employees':('employee','e.EmployeeID'),
                   'dealerships':('dealership','d.DealershipID'), 'sales':('sale','s.SaleID'), 'services':('service','r.ServiceID'), 'appointments':('appointment','a.AppointmentID')}
        entity = path.stem
        singular, pk = mapping[entity]
        args = '' if entity == 'vehicles' else ', id=' + pk
        hidden = '<input type="hidden" name="vin" value="{{ v.VIN }}">' if entity == 'vehicles' else ''
        restock = '''{% if s.RestockStatus is none %}<label for="restock-{{ s.SaleID }}">Return vehicle to</label><select name="restock_status" id="restock-{{ s.SaleID }}" required><option value="">Choose status</option><option>Available</option><option>Reserved</option></select>{% endif %}''' if entity == 'sales' else ''
        form = f'''<form method="POST" action="{{{{ url_for('web.delete_{singular}'{args}) }}}}" class="delete-form" data-confirm="Delete this record?">
                <input type="hidden" name="_csrf" value="{{{{ csrf_token() }}}}">{hidden}{restock}
                <button type="submit" class="btn btn-danger">Delete</button>
            </form>'''
        s,n = re.subn(r'<a href="/[^\"]+/delete/[^\"]*"[^>]*>Delete</a>', lambda m: form, s)
        if n != 1: raise RuntimeError(f'Deletion anchor missing in {path.name}: {n}')
        s=s.replace('<table>', '<div class="table-scroll"><table>').replace('</table>', '</table></div>\n    {% include "pagination.html" %}')
        collection = 'records' if entity == 'services' else entity
        s=s.replace('{% include "pagination.html" %}', f'{{% if not {collection} %}}<p class="subtle">No records found.</p>{{% endif %}}\n    {{% include "pagination.html" %}}')
        if entity == 'vehicles':
            s=s.replace('<th>Bought Price</th>', '<th>Bought Price</th>\n            <th>Listing Price</th>')
            s=s.replace('<td>{{ v.BoughtPrice|money }}</td>', '<td>{{ v.BoughtPrice|money }}</td>\n            <td>{{ v.ListingPrice|money }}</td>')
            for status in ('All','Available','Sold','Reserved'):
                s=s.replace(f'/vehicles?status={status}&mode={{{{ mode }}}}', "{{ url_for('web.vehicles', status='"+status+"', mode=mode) }}")
        if entity == 'appointments':
            s=s.replace('<th>Vehicle</th>','<th>Vehicle</th>\n            <th>Dealership</th>')
            s=s.replace('<td>{{ a.Brand }} {{ a.Model }}</td>', '<td>{{ a.Brand }} {{ a.Model }}</td>\n            <td>{{ a.DealershipCity or "Unassigned" }}</td>')
        s=s.replace('<th>Mechanic</th>', '<th>Employee</th>')
    def nav(m):
        pathpart, _, query = m[1].partition('?')
        if '{{' in pathpart: return m[0]
        pieces=pathpart.strip('/').split('/')
        if pathpart == '/': endpoint,args='home',''
        elif pieces[0]=='action': endpoint,args='action_choose',f", action='{pieces[1]}'"
        elif pathpart=='/supporting-schema': endpoint,args='supporting_schema',''
        elif len(pieces)==2 and pieces[1]=='add':
            singular={'customers':'customer','vehicles':'vehicle','employees':'employee','dealerships':'dealership','sales':'sale','services':'service','appointments':'appointment'}[pieces[0]]
            endpoint,args='add_'+singular,''
        elif len(pieces)==1: endpoint,args=pieces[0],''
        else: return m[0]
        if query.startswith('mode='): args += ", mode='" + query[5:] + "'"
        return 'href="{{ url_for(\'web.' + endpoint + "'"+args+') }}"'
    s=re.sub(r'href="(/[^\"]*)"', nav,s)
    s=s.replace('\u2014','-')
    path.write_text(s)

p=root/'base.html';s=p.read_text()
s=s.replace('<html>', '<html lang="en">').replace('<head>', '<head>\n    <meta charset="utf-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1">')
s=s.replace('<nav>', '<nav>\n        {% if session.get("user") %}')
s=s.replace('    </nav>', '''        <form method="POST" action="{{ url_for('logout') }}" class="logout-form">
            <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
            <button type="submit" class="btn btn-secondary">Sign out</button>
        </form>
        {% else %}<span class="brand">Car Dealership</span>{% endif %}
    </nav>''')
s=s.replace('    </style>', '''        .delete-form { display: inline-block; }
        .delete-form select { width: auto; display: block; margin-bottom: 8px; }
        .logout-form { margin-left: auto; }
        .pagination { position: static; background: transparent; color: var(--text); box-shadow: none; border: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-top: 20px; }
        nav.pagination a { color: var(--brand-700); background: white; }
        .flash-warning { background: var(--gold-100); padding: 12px; }
        @media (max-width: 600px) { .dashboard-actions, .stats { grid-template-columns: 1fr; } }
    </style>''')
s=s.replace('</body>', '    <script src="{{ url_for(\'static\', filename=\'app.js\') }}" defer></script>\n</body>')
p.write_text(s)
p=root/'supporting_schema.html';s=p.read_text()
start=s.index('<div class="card">');end=s.index('<div class="card">',start+1)
s=s[:start]+'''<div class="card">
    <h2>Database schema</h2>
    <p class="page-lead">Tables and relationships below are read from the connected database. schema.sql is the canonical initialization file.</p>
    <details><summary>Original conceptual ER diagram (historical reference)</summary>
        <img class="diagram-image" src="{{ url_for('web.er_diagram_image') }}" alt="Original conceptual ER diagram">
        <p class="subtle">This legacy diagram and CarDealership.mwb are not migration scripts and may differ from the live schema.</p>
    </details>
</div>

'''+s[end:];p.write_text(s)
p=root/'car.csv'
with p.open(newline='') as f:
 reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
with (root/'transactions.csv').open(newline='') as f: sold={r['VIN #'] for r in csv.DictReader(f)}
for row in rows:
 if row['VIN'] in sold: row['InventoryStatus']='Sold'
with p.open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=headers,lineterminator='\n');writer.writeheader();writer.writerows(rows)

p=root/'dealership_queries.sql';s=p.read_text();s=s[s.index('-- SECTION 2:'):]
s='''-- Report-only SQL for the canonical schema.sql definitions.
-- Select DB_NAME first, for example: mysql -D cardealership < dealership_queries.sql
-- Initialize using python manage.py init-db. This file does not create or migrate tables.

'''+s
for old,new in [('sr.date','sr.ServiceDate'),('t.date','t.SaleDate'),('ca.dealership','ca.DealershipID'),('c.dealership','c.DealershipID'),('e.name','e.EmployeeName'),('c.name','c.CustomerName')]:s=s.replace(old,new)
for old,new in [('dealerships','Dealership'),('customers','Customer'),('employee','Employee'),('car','Vehicle'),('transactions','SaleTransaction'),('serviceappointment','ServiceAppointment'),('servicerecord','ServiceRecord')]:
 s=re.sub(r'\b(FROM|JOIN)\s+'+old+r'\b',lambda m:m[1]+' '+new,s,flags=re.I)
for old,new in [('dealership_id','DealershipID'),('customer_id','CustomerID'),('employee_id','EmployeeID'),('credit_score','CreditScore'),('inventory_status','InventoryStatus'),('listing_price','ListingPrice'),('bought_price','BoughtPrice'),('sold_price','SoldPrice'),('sale_id','SaleID'),('service_id','ServiceID'),('appointment_id','AppointmentID'),('appointment_date','AppointmentDate'),('service_done','ServiceDone')]:
 s=re.sub(r'\b'+old+r'\b',new,s)
s=s.replace('SELECT CustomerID, name', 'SELECT CustomerID, CustomerName').replace('SELECT EmployeeID, name', 'SELECT EmployeeID, EmployeeName')
s=re.sub(r'\bdate\b','SaleDate',s)
s=s.replace('SELECT d.city,\n       COUNT(c.vin)', 'SELECT d.DealershipID, d.city,\n       COUNT(c.vin)').replace('GROUP  BY d.city;', 'GROUP BY d.DealershipID, d.city;')
a=s.index('-- 4.4');b=s.index('-- 4.5');s=s[:a]+'''-- 4.4 Average credit score, each purchasing customer counted once
SELECT AVG(c.CreditScore) AS avg_credit_score
FROM Customer c
WHERE EXISTS (SELECT 1 FROM SaleTransaction t WHERE t.CustomerID=c.CustomerID);

'''+s[b:]
a=s.index('-- 6.3');b=s.index('-- 6.4');s=s[:a]+'''-- 6.3 Employees who have never made a sale, including nullable legacy assignments
SELECT e.EmployeeID, e.EmployeeName, e.Position
FROM Employee e
WHERE NOT EXISTS (SELECT 1 FROM SaleTransaction t WHERE t.EmployeeID=e.EmployeeID);

'''+s[b:];p.write_text(s)
