from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import mysql.connector

app = Flask(__name__, template_folder='.')
app.secret_key = "dealership123"  # needed for flash messages
PROJECT_ROOT = Path(__file__).resolve().parent

# ============================================================
# DATABASE CONNECTION
# ============================================================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="",
        database="cardealership"
    )


def get_supporting_schema():
    return [
        {
            'display_name': 'Dealership',
            'table_name': 'Dealership',
            'description': 'The dealership that has used car inventory in our used cars dealership mini world.',
            'primary_key': 'DealershipID',
            'foreign_keys': [],
            'columns': [
                {'name': 'DealershipID', 'type': 'INT', 'role': 'Primary key', 'domain': 'Any integer > 0'},
                {'name': 'Address', 'type': 'VARCHAR(255)', 'role': 'Attribute', 'domain': 'Any string'},
                {'name': 'City', 'type': 'VARCHAR(100)', 'role': 'Attribute', 'domain': 'Any string'},
                {'name': 'State', 'type': 'VARCHAR(2)', 'role': 'Attribute', 'domain': 'Any valid US state abbreviation'},
                {'name': 'ZipCode', 'type': 'VARCHAR(10)', 'role': 'Attribute', 'domain': 'Any valid ZIP code'},
            ],
        },
        {
            'display_name': 'Vehicle (Car)',
            'table_name': 'Vehicle',
            'description': 'A car that is stored in our system, along with its dealership location and defining characteristics.',
            'primary_key': 'VIN',
            'foreign_keys': [
                {'column': 'DealershipID', 'references': 'Dealership.DealershipID'},
            ],
            'columns': [
                {'name': 'VIN', 'type': 'VARCHAR(50)', 'role': 'Primary key', 'domain': 'Any string'},
                {'name': 'Model', 'type': 'VARCHAR(100)', 'role': 'Attribute', 'domain': 'Any string'},
                {'name': 'Type', 'type': 'VARCHAR(50)', 'role': 'Attribute', 'domain': 'SUV, Sedan, Truck, Coupe, Hatchback, Wagon'},
                {'name': 'Year', 'type': 'INT', 'role': 'Attribute', 'domain': '1886-2027'},
                {'name': 'Brand', 'type': 'VARCHAR(100)', 'role': 'Attribute', 'domain': 'Any string'},
                {'name': 'DealershipID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
                {'name': 'Miles', 'type': 'INT', 'role': 'Attribute', 'domain': 'Any integer >= 0'},
                {'name': 'BoughtPrice', 'type': 'DECIMAL(10, 2)', 'role': 'Attribute', 'domain': 'Any decimal > 0'},
                {'name': 'ListingPrice', 'type': 'DECIMAL(10, 2)', 'role': 'Attribute', 'domain': 'Any decimal > 0'},
                {'name': 'InventoryStatus', 'type': 'VARCHAR(20)', 'role': 'Attribute', 'domain': 'Available, Sold, Reserved'},
            ],
        },
        {
            'display_name': 'Customer',
            'table_name': 'Customer',
            'description': 'A customer that buys used cars in our used car dealership.',
            'primary_key': 'CustomerID',
            'foreign_keys': [],
            'columns': [
                {'name': 'CustomerID', 'type': 'INT', 'role': 'Primary key', 'domain': 'Any integer > 0'},
                {'name': 'CustomerName', 'type': 'VARCHAR(100)', 'role': 'Attribute', 'domain': 'Any string'},
                {'name': 'CreditScore', 'type': 'INT', 'role': 'Attribute', 'domain': 'Any integer 300-850'},
                {'name': 'Email', 'type': 'VARCHAR(255)', 'role': 'Attribute', 'domain': 'Any valid email'},
                {'name': 'PhoneNumber', 'type': 'VARCHAR(20)', 'role': 'Attribute', 'domain': 'Any valid phone number'},
                {'name': 'Loan', 'type': 'DECIMAL(10, 2)', 'role': 'Attribute', 'domain': 'Any decimal > 0 or NULL'},
            ],
        },
        {
            'display_name': 'Employee',
            'table_name': 'Employee',
            'description': 'An employee who tries to sell a used car in our used car dealership mini world.',
            'primary_key': 'EmployeeID',
            'foreign_keys': [
                {'column': 'DealershipID', 'references': 'Dealership.DealershipID'},
            ],
            'columns': [
                {'name': 'EmployeeID', 'type': 'INT', 'role': 'Primary key', 'domain': 'Any integer > 0'},
                {'name': 'EmployeeName', 'type': 'VARCHAR(100)', 'role': 'Attribute', 'domain': 'Any string'},
                {'name': 'PhoneNumber', 'type': 'VARCHAR(20)', 'role': 'Attribute', 'domain': 'Any valid phone number'},
                {'name': 'Email', 'type': 'VARCHAR(255)', 'role': 'Attribute', 'domain': 'Any valid email'},
                {'name': 'Position', 'type': 'VARCHAR(50)', 'role': 'Attribute', 'domain': 'Salesperson, Mechanic, Manager, CEO, Security, Janitor'},
                {'name': 'DealershipID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
            ],
        },
        {
            'display_name': 'SaleTransaction (Transaction)',
            'table_name': 'SaleTransaction',
            'description': 'A transaction involving a customer, employee, and car is included in our dealership mini world.',
            'primary_key': 'SaleID',
            'foreign_keys': [
                {'column': 'CustomerID', 'references': 'Customer.CustomerID'},
                {'column': 'EmployeeID', 'references': 'Employee.EmployeeID'},
                {'column': 'VIN', 'references': 'Vehicle.VIN'},
            ],
            'columns': [
                {'name': 'SaleID', 'type': 'INT', 'role': 'Primary key', 'domain': 'Any integer > 0'},
                {'name': 'SaleDate', 'type': 'DATE', 'role': 'Attribute', 'domain': 'Any valid date'},
                {'name': 'CustomerID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
                {'name': 'EmployeeID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
                {'name': 'VIN', 'type': 'VARCHAR(50)', 'role': 'Foreign key', 'domain': 'Any string'},
                {'name': 'SoldPrice', 'type': 'DECIMAL(10, 2)', 'role': 'Attribute', 'domain': 'Any decimal > 0'},
            ],
        },
        {
            'display_name': 'ServiceRecord',
            'table_name': 'ServiceRecord',
            'description': 'Record of service being done to used cars in the dealership mini world.',
            'primary_key': 'ServiceID',
            'foreign_keys': [
                {'column': 'VIN', 'references': 'Vehicle.VIN'},
                {'column': 'EmployeeID', 'references': 'Employee.EmployeeID'},
            ],
            'columns': [
                {'name': 'ServiceID', 'type': 'INT', 'role': 'Primary key', 'domain': 'Any integer > 0'},
                {'name': 'VIN', 'type': 'VARCHAR(50)', 'role': 'Foreign key', 'domain': 'Any string'},
                {'name': 'Cost', 'type': 'DECIMAL(10, 2)', 'role': 'Attribute', 'domain': 'Any decimal > 0'},
                {'name': 'ServiceDate', 'type': 'DATE', 'role': 'Attribute', 'domain': 'Any valid date'},
                {'name': 'ServiceDone', 'type': 'VARCHAR(100)', 'role': 'Attribute', 'domain': 'Brakes, Oil Change, Tires'},
                {'name': 'EmployeeID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
            ],
        },
        {
            'display_name': 'ServiceAppointment',
            'table_name': 'ServiceAppointment',
            'description': 'Appointment record of car services done in used car dealership Mini World.',
            'primary_key': 'AppointmentID',
            'foreign_keys': [
                {'column': 'EmployeeID', 'references': 'Employee.EmployeeID'},
                {'column': 'CustomerID', 'references': 'Customer.CustomerID'},
                {'column': 'VIN', 'references': 'Vehicle.VIN'},
                {'column': 'DealershipID', 'references': 'Dealership.DealershipID'},
            ],
            'columns': [
                {'name': 'AppointmentID', 'type': 'INT', 'role': 'Primary key', 'domain': 'Any integer > 0'},
                {'name': 'EmployeeID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
                {'name': 'CustomerID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
                {'name': 'VIN', 'type': 'VARCHAR(50)', 'role': 'Foreign key', 'domain': 'Any string'},
                {'name': 'Status', 'type': 'VARCHAR(20)', 'role': 'Attribute', 'domain': 'Scheduled, Completed, Cancelled, Delayed'},
                {'name': 'AppointmentDate', 'type': 'DATE', 'role': 'Attribute', 'domain': 'Any valid date'},
                {'name': 'DealershipID', 'type': 'INT', 'role': 'Foreign key', 'domain': 'Any integer > 0'},
            ],
        },
    ]

# ============================================================
# HOME PAGE — Dashboard
# ============================================================
@app.route('/')
def home():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get counts for dashboard
    cursor.execute("SELECT COUNT(*) AS count FROM Customer")
    customer_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM Vehicle")
    vehicle_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM Employee")
    employee_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM SaleTransaction")
    sale_count = cursor.fetchone()['count']

    cursor.execute("SELECT COALESCE(SUM(SoldPrice), 0) AS total FROM SaleTransaction")
    total_revenue = cursor.fetchone()['total']

    db.close()
    return render_template('home.html',
        customer_count=customer_count,
        vehicle_count=vehicle_count,
        employee_count=employee_count,
        sale_count=sale_count,
        total_revenue=total_revenue
    )

# ============================================================
# ACTION CHOOSER
# ============================================================
@app.route('/action/<action>')
def action_choose(action):
    return render_template('action_choose.html', action=action)


@app.route('/supporting-schema')
def supporting_schema():
    schema_entities = get_supporting_schema()
    relationship_map = [
        {
            'source': f"{entity['table_name']}.{foreign_key['column']}",
            'target': foreign_key['references'],
        }
        for entity in schema_entities
        for foreign_key in entity['foreign_keys']
    ]
    return render_template(
        'supporting_schema.html',
        schema_entities=schema_entities,
        relationship_map=relationship_map,
        schema_table_count=len(schema_entities),
        schema_fk_count=len(relationship_map),
        schema_column_count=sum(len(entity['columns']) for entity in schema_entities),
        diagram_url='https://drive.google.com/file/d/1qE63pMoRr8kKwduSugy9wBy-7HfUvBIo/view?usp=sharing',
        diagram_preview_url='https://drive.google.com/file/d/1qE63pMoRr8kKwduSugy9wBy-7HfUvBIo/preview',
        er_diagram_url='https://drive.google.com/file/d/1j3ck5XOo52yQ4AiW-rxGcCxJ2qOTRdJm/view?usp=sharing',
    )


@app.route('/er-diagram-image')
def er_diagram_image():
    return send_file(PROJECT_ROOT / 'ER_Diagram.png', mimetype='image/png')

# ============================================================
# CUSTOMERS
# ============================================================
@app.route('/customers')
def customers():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer ORDER BY CustomerID")
    customers = cursor.fetchall()
    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('customers.html', customers=customers, mode=mode)

@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            # Auto-generate next ID
            cursor.execute("SELECT COALESCE(MAX(CustomerID), 0) + 1 AS next_id FROM Customer")
            next_id = cursor.fetchone()['next_id']
            # Handle optional fields
            phone = request.form.get('phone') or None
            loan = request.form.get('loan') or None
            cursor.execute(
                "INSERT INTO Customer (CustomerID, CustomerName, CreditScore, Email, PhoneNumber, Loan) VALUES (%s, %s, %s, %s, %s, %s)",
                (next_id, request.form['name'], request.form['credit'],
                 request.form['email'], phone, loan)
            )
            db.commit()
            flash(f"Added {request.form['name']}!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('customers'))
    return render_template('add_customer.html')

@app.route('/customers/delete/<int:id>')
def delete_customer(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM Customer WHERE CustomerID = %s", (id,))
        db.commit()
        flash("Customer deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('customers'))

# ============================================================
# VEHICLES
# ============================================================
@app.route('/vehicles')
def vehicles():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    status_filter = request.args.get('status', 'All')
    if status_filter != 'All':
        cursor.execute("SELECT * FROM Vehicle WHERE InventoryStatus = %s ORDER BY VIN", (status_filter,))
    else:
        cursor.execute("SELECT * FROM Vehicle ORDER BY VIN")

    vehicles = cursor.fetchall()
    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('vehicles.html', vehicles=vehicles, current_filter=status_filter, mode=mode)

@app.route('/vehicles/add', methods=['GET', 'POST'])
def add_vehicle():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO Vehicle (VIN, Model, Type, Year, Brand, DealershipID, Miles, BoughtPrice, InventoryStatus) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (request.form['vin'], request.form['model'], request.form['type'],
                 request.form['year'], request.form['brand'], request.form['dealership_id'],
                 request.form['miles'], request.form['bought_price'], request.form['status'])
            )
            db.commit()
            flash(f"Added {request.form['brand']} {request.form['model']}!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('vehicles'))
    return render_template('add_vehicle.html')

# ============================================================
# EMPLOYEES
# ============================================================
@app.route('/employees')
def employees():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, d.City AS DealershipCity
        FROM Employee e
        JOIN Dealership d ON e.DealershipID = d.DealershipID
        ORDER BY e.EmployeeID
    """)
    employees = cursor.fetchall()
    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('employees.html', employees=employees, mode=mode)

@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT COALESCE(MAX(EmployeeID), 0) + 1 AS next_id FROM Employee")
            next_id = cursor.fetchone()['next_id']
            phone = request.form.get('phone') or None
            cursor.execute(
                "INSERT INTO Employee (EmployeeID, EmployeeName, PhoneNumber, Email, Position, DealershipID) VALUES (%s, %s, %s, %s, %s, %s)",
                (next_id, request.form['name'], phone,
                 request.form['email'], request.form['position'], request.form['dealership_id'])
            )
            db.commit()
            flash(f"Added {request.form['name']}!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('employees'))
    return render_template('add_employee.html')

@app.route('/employees/delete/<int:id>')
def delete_employee(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM Employee WHERE EmployeeID = %s", (id,))
        db.commit()
        flash("Employee deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('employees'))

# ============================================================
# DEALERSHIPS
# ============================================================
@app.route('/dealerships')
def dealerships():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.*, COUNT(v.VIN) AS CarCount
        FROM Dealership d
        LEFT JOIN Vehicle v ON d.DealershipID = v.DealershipID
        GROUP BY d.DealershipID
    """)
    dealerships = cursor.fetchall()
    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('dealerships.html', dealerships=dealerships, mode=mode)

@app.route('/dealerships/add', methods=['GET', 'POST'])
def add_dealership():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT COALESCE(MAX(DealershipID), 0) + 1 AS next_id FROM Dealership")
            next_id = cursor.fetchone()['next_id']
            cursor.execute(
                "INSERT INTO Dealership (DealershipID, Address, City, State, ZipCode) VALUES (%s, %s, %s, %s, %s)",
                (next_id, request.form['address'], request.form['city'],
                 request.form['state'], request.form['zipcode'])
            )
            db.commit()
            flash(f"Added dealership in {request.form['city']}!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('dealerships'))
    return render_template('add_dealership.html')

@app.route('/dealerships/delete/<int:id>')
def delete_dealership(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM Dealership WHERE DealershipID = %s", (id,))
        db.commit()
        flash("Dealership deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('dealerships'))

# ============================================================
# SALES
# ============================================================
@app.route('/sales')
def sales():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.SaleID, s.SaleDate, c.CustomerName, e.EmployeeName,
               v.Brand, v.Model, s.SoldPrice, v.BoughtPrice, (s.SoldPrice - v.BoughtPrice) AS Profit
        FROM SaleTransaction s
        JOIN Customer c ON s.CustomerID = c.CustomerID
        JOIN Employee e ON s.EmployeeID = e.EmployeeID
        JOIN Vehicle v ON s.VIN = v.VIN
        ORDER BY s.SaleDate DESC
    """)
    sales = cursor.fetchall()

    cursor.execute("SELECT COALESCE(SUM(SoldPrice), 0) AS total FROM SaleTransaction")
    total = cursor.fetchone()['total']

    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('sales.html', sales=sales, total_revenue=total, mode=mode)

@app.route('/sales/add', methods=['GET', 'POST'])
def add_sale():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT COALESCE(MAX(SaleID), 0) + 1 AS next_id FROM SaleTransaction")
            next_id = cursor.fetchone()['next_id']
            cursor.execute(
                "INSERT INTO SaleTransaction (SaleID, SaleDate, CustomerID, EmployeeID, VIN, SoldPrice) VALUES (%s, %s, %s, %s, %s, %s)",
                (next_id, request.form['date'], request.form['customer_id'],
                 request.form['employee_id'], request.form['vin'], request.form['sold_price'])
            )
            db.commit()
            flash("Sale added!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('sales'))
    return render_template('add_sale.html')

@app.route('/sales/delete/<int:id>')
def delete_sale(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM SaleTransaction WHERE SaleID = %s", (id,))
        db.commit()
        flash("Sale deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('sales'))

# ============================================================
# VEHICLES — Delete
# ============================================================
@app.route('/vehicles/delete/<path:vin>')
def delete_vehicle(vin):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM Vehicle WHERE VIN = %s", (vin,))
        db.commit()
        flash("Vehicle deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('vehicles'))

# ============================================================
# SERVICE RECORDS
# ============================================================
@app.route('/services')
def services():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT sr.ServiceID, sr.ServiceDate, sr.ServiceDone, sr.Cost,
               sr.VIN, v.Brand, v.Model, e.EmployeeName
        FROM ServiceRecord sr
        JOIN Vehicle v ON sr.VIN = v.VIN
        JOIN Employee e ON sr.EmployeeID = e.EmployeeID
        ORDER BY sr.ServiceDate DESC
    """)
    records = cursor.fetchall()
    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('services.html', records=records, mode=mode)

@app.route('/services/add', methods=['GET', 'POST'])
def add_service():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT COALESCE(MAX(ServiceID), 0) + 1 AS next_id FROM ServiceRecord")
            next_id = cursor.fetchone()['next_id']
            cursor.execute(
                "INSERT INTO ServiceRecord (ServiceID, VIN, Cost, ServiceDate, ServiceDone, EmployeeID) VALUES (%s, %s, %s, %s, %s, %s)",
                (next_id, request.form['vin'], request.form['cost'],
                 request.form['date'], request.form['service_done'], request.form['employee_id'])
            )
            db.commit()
            flash("Service record added!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('services'))
    return render_template('add_service.html')

@app.route('/services/delete/<int:id>')
def delete_service(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM ServiceRecord WHERE ServiceID = %s", (id,))
        db.commit()
        flash("Service record deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('services'))

# ============================================================
# SERVICE APPOINTMENTS
# ============================================================
@app.route('/appointments')
def appointments():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT sa.AppointmentID, sa.AppointmentDate, sa.Status,
               c.CustomerName, e.EmployeeName, v.Brand, v.Model
        FROM ServiceAppointment sa
        JOIN Customer c ON sa.CustomerID = c.CustomerID
        JOIN Employee e ON sa.EmployeeID = e.EmployeeID
        JOIN Vehicle v ON sa.VIN = v.VIN
        ORDER BY sa.AppointmentDate DESC
    """)
    appointments = cursor.fetchall()
    mode = request.args.get('mode', 'full')
    db.close()
    return render_template('appointments.html', appointments=appointments, mode=mode)

@app.route('/appointments/add', methods=['GET', 'POST'])
def add_appointment():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT COALESCE(MAX(AppointmentID), 0) + 1 AS next_id FROM ServiceAppointment")
            next_id = cursor.fetchone()['next_id']
            cursor.execute(
                "INSERT INTO ServiceAppointment (AppointmentID, EmployeeID, CustomerID, VIN, Status, AppointmentDate, DealershipID) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (next_id, request.form['employee_id'], request.form['customer_id'],
                 request.form['vin'], request.form['status'], request.form['date'],
                 request.form['dealership_id'])
            )
            db.commit()
            flash("Appointment added!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e}", "error")
        db.close()
        return redirect(url_for('appointments'))
    return render_template('add_appointment.html')

@app.route('/appointments/delete/<int:id>')
def delete_appointment(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM ServiceAppointment WHERE AppointmentID = %s", (id,))
        db.commit()
        flash("Appointment deleted!", "success")
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "error")
    db.close()
    return redirect(url_for('appointments'))

# ============================================================
# RUN THE APP
# ============================================================
if __name__ == '__main__':
    app.run(debug=False)


# to run the app, use the command: python InterfaceDatabase.py
# to access the website http://localhost:5000/
# to run using Ngrok use ngrok.exe http 5000
