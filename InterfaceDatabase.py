"""Server-rendered dealership application. Run through create_app(), never import-time I/O."""
from datetime import date, timedelta
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from flask import (Blueprint, Flask, abort, current_app, flash, redirect, render_template,
                   request, send_file, session, url_for)
import mysql.connector
from werkzeug.security import check_password_hash

import db
from validation import (APPOINTMENT_STATUSES, INVENTORY_STATUSES, POSITIONS, SERVICES,
                        VEHICLE_TYPES, ValidationError, choice, integer, text, values_for)

ROOT = Path(__file__).resolve().parent
web = Blueprint('web', __name__)
# Identifiers here are code-owned, never supplied by a request.
ENTITIES = {
    'customers': ('Customer', 'CustomerID', 'customer', 'CustomerName,CreditScore,Email,PhoneNumber,Loan'),
    'vehicles': ('Vehicle', 'VIN', 'vehicle', 'VIN,Model,Type,Year,Brand,DealershipID,Miles,BoughtPrice,ListingPrice,InventoryStatus'),
    'employees': ('Employee', 'EmployeeID', 'employee', 'EmployeeName,PhoneNumber,Email,Position,DealershipID'),
    'dealerships': ('Dealership', 'DealershipID', 'dealership', 'Address,City,State,ZipCode'),
    'sales': ('SaleTransaction', 'SaleID', 'sale', 'SaleDate,CustomerID,EmployeeID,VIN,SoldPrice'),
    'services': ('ServiceRecord', 'ServiceID', 'service', 'VIN,Cost,ServiceDate,ServiceDone,EmployeeID'),
    'appointments': ('ServiceAppointment', 'AppointmentID', 'appointment', 'EmployeeID,CustomerID,VIN,Status,AppointmentDate,DealershipID'),
}
LIST_SQL = {
    'customers': 'SELECT * FROM Customer ORDER BY CustomerID',
    'vehicles': 'SELECT * FROM Vehicle {where} ORDER BY VIN',
    'employees': '''SELECT e.*, d.City AS DealershipCity FROM Employee e
        LEFT JOIN Dealership d ON e.DealershipID=d.DealershipID ORDER BY e.EmployeeID''',
    'dealerships': '''SELECT d.*, COALESCE(v.CarCount,0) AS CarCount FROM Dealership d
        LEFT JOIN (SELECT DealershipID, COUNT(*) AS CarCount FROM Vehicle
        WHERE InventoryStatus IN ('Available','Reserved') GROUP BY DealershipID) v
        ON v.DealershipID=d.DealershipID ORDER BY d.DealershipID''',
    'sales': '''SELECT s.*, c.CustomerName, e.EmployeeName, v.Brand, v.Model,
        v.BoughtPrice, s.SoldPrice-v.BoughtPrice AS Profit FROM SaleTransaction s
        LEFT JOIN Customer c ON s.CustomerID=c.CustomerID
        LEFT JOIN Employee e ON s.EmployeeID=e.EmployeeID
        LEFT JOIN Vehicle v ON s.VIN=v.VIN ORDER BY s.SaleDate DESC, s.SaleID DESC''',
    'services': '''SELECT sr.*, v.Brand, v.Model, e.EmployeeName FROM ServiceRecord sr
        LEFT JOIN Vehicle v ON sr.VIN=v.VIN LEFT JOIN Employee e ON sr.EmployeeID=e.EmployeeID
        ORDER BY sr.ServiceDate DESC, sr.ServiceID DESC''',
    'appointments': '''SELECT sa.*, c.CustomerName, e.EmployeeName, v.Brand, v.Model, d.City AS DealershipCity
        FROM ServiceAppointment sa LEFT JOIN Customer c ON sa.CustomerID=c.CustomerID
        LEFT JOIN Employee e ON sa.EmployeeID=e.EmployeeID LEFT JOIN Vehicle v ON sa.VIN=v.VIN
        LEFT JOIN Dealership d ON sa.DealershipID=d.DealershipID
        ORDER BY sa.AppointmentDate DESC, sa.AppointmentID DESC''',
}


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def create_app(config=None):
    app = Flask(__name__, template_folder=str(ROOT), static_folder=str(ROOT / 'static'))
    app.config.from_mapping(db.settings())
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY'), ADMIN_USERNAME=os.getenv('ADMIN_USERNAME'),
                      ADMIN_PASSWORD_HASH=os.getenv('ADMIN_PASSWORD_HASH'), PAGE_SIZE=50,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.getenv('APP_ENV') == 'production',
                      PERMANENT_SESSION_LIFETIME=timedelta(minutes=30), MAX_CONTENT_LENGTH=65536)
    if config:
        app.config.update(config)
    if not isinstance(app.config['SECRET_KEY'], str) or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Set SECRET_KEY to a random secret of at least 32 characters. See README.')
    if not app.config['ADMIN_USERNAME'] or not app.config['ADMIN_PASSWORD_HASH']:
        raise RuntimeError('Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH. See README.')
    password_hash = app.config['ADMIN_PASSWORD_HASH']
    if not isinstance(password_hash, str) or not password_hash.startswith(('scrypt:', 'pbkdf2:')) or password_hash.count('$') != 2:
        raise RuntimeError('ADMIN_PASSWORD_HASH must be a Werkzeug password hash, not a password.')
    auth_version = hashlib.sha256(password_hash.encode()).hexdigest()

    @app.before_request
    def protect_requests():
        if request.endpoint is None:  # Let Flask return 404/405 without entering a view.
            return None
        public = request.endpoint in ('login', 'static')
        authenticated = (session.get('user') == app.config['ADMIN_USERNAME']
                         and session.get('auth_version') == auth_version)
        if not public and not authenticated:
            if request.method not in ('GET', 'HEAD'):
                abort(401, description='Sign in before changing records.')
            return redirect(url_for('login'))
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            supplied = request.form.get('_csrf', '')
            expected = session.get('_csrf', '')
            if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
                abort(400, description='The form expired or is invalid. Reload the page and try again.')

    @app.after_request
    def secure_response(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "img-src 'self'; frame-src https://drive.google.com; form-action 'self'; base-uri 'self'; frame-ancestors 'self'")
        return response

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            # Always check a bounded password to avoid revealing which username matched by hash timing.
            valid = len(password) <= 256 and check_password_hash(password_hash, password)
            if not (hmac.compare_digest(username.encode(), app.config['ADMIN_USERNAME'].encode()) and valid):
                return render_template('login.html', error='Invalid username or password.'), 401
            session.clear()
            session['user'] = app.config['ADMIN_USERNAME']
            session['auth_version'] = auth_version
            session.permanent = True
            csrf_token()  # Rotate the token at the authentication boundary.
            return redirect(url_for('web.home'), code=303)
        return render_template('login.html')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'), code=303)

    @app.errorhandler(mysql.connector.Error)
    def database_error(error):
        app.logger.warning('Database operation failed (errno=%s)', error.errno)
        return render_template('error.html', message='Database unavailable or schema not initialized. Check configuration and README.', code=503), 503

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return render_template('error.html', message=str(error), code=400), 400

    for code in (400, 401, 403, 404, 405, 409, 413, 500):
        def http_error(error):
            message = error.description if error.code != 500 else 'An unexpected error occurred. Please try again.'
            return render_template('error.html', message=message, code=error.code), error.code
        app.register_error_handler(code, http_error)

    app.jinja_env.globals.update(csrf_token=csrf_token)
    app.jinja_env.filters['money'] = lambda value: 'Not recorded' if value is None else f'${value:,.2f}'
    app.jinja_env.filters['number'] = lambda value: 'Not recorded' if value is None else f'{value:,}'

    @app.context_processor
    def form_context():
        return dict(values=request.form, vehicle_types=VEHICLE_TYPES, positions=POSITIONS,
                    appointment_statuses=APPOINTMENT_STATUSES, service_types=SERVICES, max_year=date.today().year + 1)

    app.register_blueprint(web)
    return app


@web.get('/')
def home():
    with db.cursor() as cur:
        counts = {}
        for entity, name in [('customers', 'customer'), ('vehicles', 'vehicle'), ('employees', 'employee'), ('sales', 'sale')]:
            cur.execute(f'SELECT COUNT(*) AS count FROM {ENTITIES[entity][0]}')
            counts[name + '_count'] = cur.fetchone()['count']
        cur.execute('SELECT COALESCE(SUM(SoldPrice),0) AS total FROM SaleTransaction')
        counts['total_revenue'] = cur.fetchone()['total']
    return render_template('home.html', **counts)


@web.get('/action/<action>')
def action_choose(action):
    if action not in ('add', 'delete', 'view'):
        abort(404)
    return render_template('action_choose.html', action=action)


def list_records(entity):
    mode = request.args.get('mode', 'full')
    if mode not in ('full', 'view', 'delete'):
        abort(400, description='Invalid display mode.')
    page = integer({'page': request.args.get('page', '1')}, 'page', 1, 1000000)
    limit = current_app.config['PAGE_SIZE']
    where, params = '', ()
    status = request.args.get('status', 'All')
    if entity == 'vehicles':
        if status not in ('All', *INVENTORY_STATUSES):
            abort(400, description='Invalid inventory status.')
        if status != 'All':
            where, params = 'WHERE InventoryStatus=%s', (status,)
    with db.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) AS count FROM {ENTITIES[entity][0]} {where}', params)
        total_rows = cur.fetchone()['count']
        cur.execute(LIST_SQL[entity].format(where=where) + ' LIMIT %s OFFSET %s', params + (limit, (page - 1) * limit))
        rows = cur.fetchall()
        revenue = None
        if entity == 'sales':
            cur.execute('SELECT COALESCE(SUM(SoldPrice),0) AS total FROM SaleTransaction')
            revenue = cur.fetchone()['total']
    pages = max(1, (total_rows + limit - 1) // limit)
    if page > pages:
        abort(404, description='Page not found.')
    args = {'mode': mode}
    if entity == 'vehicles':
        args['status'] = status
    pagination = dict(page=page, pages=pages, total=total_rows,
                      previous=url_for('web.' + entity, page=page-1, **args) if page > 1 else None,
                      next=url_for('web.' + entity, page=page+1, **args) if page < pages else None)
    key = 'records' if entity == 'services' else entity
    return render_template(entity + '.html', **{key: rows}, mode=mode, current_filter=status,
                           pagination=pagination, total_revenue=revenue)


def insert_record(cur, entity, values, extra_columns='', extra_values=()):
    table, _, _, columns = ENTITIES[entity]
    columns += extra_columns
    data = values + extra_values
    cur.execute(f'INSERT INTO {table} ({columns}) VALUES ({",".join(["%s"] * len(data))})', data)
    return cur.lastrowid


def add_record(entity):
    template = f'add_{ENTITIES[entity][2]}.html'
    if request.method == 'GET':
        return render_template(template)
    try:
        values = values_for(entity, request.form)
        with db.cursor(write=True) as cur:
            if entity == 'sales':
                vin = values[3]
                cur.execute('SELECT InventoryStatus FROM Vehicle WHERE VIN=%s FOR UPDATE', (vin,))
                vehicle = cur.fetchone()
                if vehicle is None:
                    raise ValidationError('Vehicle not found. Enter an existing VIN.')
                if vehicle['InventoryStatus'] not in ('Available', 'Reserved'):
                    abort(409, description='This vehicle is already sold or unavailable.')
                record_id = insert_record(cur, entity, values, ',RestockStatus', (vehicle['InventoryStatus'],))
                cur.execute("UPDATE Vehicle SET InventoryStatus='Sold' WHERE VIN=%s", (vin,))
            else:
                record_id = insert_record(cur, entity, values)
    except ValidationError as error:
        return render_template(template, error=str(error)), 400
    except mysql.connector.IntegrityError as error:
        current_app.logger.info('Creation rejected (errno=%s)', error.errno)
        return render_template(template, error='Record conflicts with existing data. Check the VIN, linked IDs and field values.'), 409
    flash(f'Added {ENTITIES[entity][2]} successfully' + (f' (ID {record_id}).' if entity != 'vehicles' else '.'), 'success')
    return redirect(url_for('web.' + entity), code=303)


def delete_record(entity, id=None):
    table, pk, singular, _ = ENTITIES[entity]
    identifier = text(request.form, 'vin', 50) if entity == 'vehicles' else id
    try:
        with db.cursor(write=True) as cur:
            if entity == 'sales':
                cur.execute('SELECT VIN FROM SaleTransaction WHERE SaleID=%s', (identifier,))
                sale = cur.fetchone()
                if sale is None:
                    abort(404, description='Sale not found. It may already have been deleted.')
                # Lock in the same order as sale creation: vehicle, then sale.
                cur.execute('SELECT VIN FROM Vehicle WHERE VIN=%s FOR UPDATE', (sale['VIN'],))
                cur.fetchone()
                cur.execute('SELECT RestockStatus FROM SaleTransaction WHERE SaleID=%s FOR UPDATE', (identifier,))
                current = cur.fetchone()
                if current is None:
                    abort(404, description='Sale not found. It may already have been deleted.')
                status = current['RestockStatus']
                if status is None:
                    status = choice(request.form, 'restock_status', ('Available', 'Reserved'))
                cur.execute('DELETE FROM SaleTransaction WHERE SaleID=%s', (identifier,))
                cur.execute('UPDATE Vehicle SET InventoryStatus=%s WHERE VIN=%s', (status, sale['VIN']))
            else:
                cur.execute(f'DELETE FROM {table} WHERE {pk}=%s', (identifier,))
                if cur.rowcount == 0:
                    abort(404, description='Record not found. It may already have been deleted.')
    except mysql.connector.IntegrityError as error:
        current_app.logger.info('Deletion rejected (errno=%s)', error.errno)
        abort(409, description='This record is referenced by other records and cannot be deleted.')
    flash(f'{singular.capitalize()} deleted.', 'success')
    return redirect(url_for('web.' + entity), code=303)


for entity, (_, _, singular, _) in ENTITIES.items():
    web.add_url_rule('/' + entity, endpoint=entity, view_func=list_records, defaults={'entity': entity}, methods=['GET'])
    web.add_url_rule('/' + entity + '/add', endpoint='add_' + singular, view_func=add_record,
                     defaults={'entity': entity}, methods=['GET', 'POST'])
    suffix = '' if entity == 'vehicles' else '/<int:id>'
    web.add_url_rule('/' + entity + '/delete' + suffix, endpoint='delete_' + singular,
                     view_func=delete_record, defaults={'entity': entity}, methods=['POST'])


@web.get('/supporting-schema')
def supporting_schema():
    entities, relationships = [], []
    with db.cursor() as cur:
        for table, pk, _, _ in ENTITIES.values():
            cur.execute(f'SHOW FULL COLUMNS FROM {table}')
            columns = [dict(name=row['Field'], type=row['Type'], role='Primary key' if row['Key'] == 'PRI' else 'Attribute',
                            domain=row['Comment'] or ('Nullable' if row['Null'] == 'YES' else 'Required')) for row in cur.fetchall()]
            cur.execute('''SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE()
                AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL''', (table,))
            fks = [dict(column=r['COLUMN_NAME'], references=f"{r['REFERENCED_TABLE_NAME']}.{r['REFERENCED_COLUMN_NAME']}") for r in cur.fetchall()]
            for col in columns:
                if any(fk['column'] == col['name'] for fk in fks):
                    col['role'] = 'Foreign key'
            entities.append(dict(display_name=table, table_name=table, primary_key=pk, columns=columns,
                                 foreign_keys=fks, description='Live database definition. See schema.sql for constraints.'))
            relationships.extend(dict(source=f"{table}.{fk['column']}", target=fk['references']) for fk in fks)
    return render_template('supporting_schema.html', schema_entities=entities, relationship_map=relationships)


@web.get('/er-diagram-image')
def er_diagram_image():
    return send_file(ROOT / 'ER_Diagram.png', mimetype='image/png')


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=False)
