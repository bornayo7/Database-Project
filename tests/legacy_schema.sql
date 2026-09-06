-- ============================================================
--  Dealership Database  --  MySQL Workbench
--  Tables: dealerships, customers, employee, car,
--          transactions, serviceappointment, servicerecord
-- ============================================================

-- ============================================================
-- SECTION 1: CREATE SCHEMA & TABLES
-- ============================================================


-- 1.1 Dealerships
CREATE TABLE IF NOT EXISTS dealerships (
    dealership_id   INT             PRIMARY KEY,
    address         VARCHAR(100)    NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    state           CHAR(2)         NOT NULL,
    zip_code        VARCHAR(10)     NOT NULL
);

-- 1.2 Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id     INT             PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    credit_score    INT,
    phone_number    VARCHAR(20),
    email           VARCHAR(100),
    loan            DECIMAL(10, 2)  DEFAULT 0.00
);

-- 1.3 Employees
CREATE TABLE IF NOT EXISTS employee (
    employee_id     INT             PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    phone_number    VARCHAR(20),
    email           VARCHAR(100),
    position        VARCHAR(50),
    dealership_id   INT,
    FOREIGN KEY (dealership_id) REFERENCES dealerships(dealership_id)
);

-- 1.4 Cars
CREATE TABLE IF NOT EXISTS car (
    vin                 VARCHAR(17)     PRIMARY KEY,
    model               VARCHAR(50)     NOT NULL,
    type                VARCHAR(50),
    year                YEAR,
    brand               VARCHAR(50),
    dealership          INT,
    miles               INT,
    bought_price        DECIMAL(10, 2),
    inventory_status    VARCHAR(20),
    listing_price       DECIMAL(10, 2),
    FOREIGN KEY (dealership) REFERENCES dealerships(dealership_id)
);

-- 1.5 Transactions
CREATE TABLE IF NOT EXISTS transactions (
    sale_id         INT             PRIMARY KEY,
    date            DATE            NOT NULL,
    customer_id     INT,
    employee_id     INT,
    vin             VARCHAR(17),
    sold_price      DECIMAL(10, 2),
    FOREIGN KEY (customer_id)   REFERENCES customers(customer_id),
    FOREIGN KEY (employee_id)   REFERENCES employee(employee_id),
    FOREIGN KEY (vin)           REFERENCES car(vin)
);

-- 1.6 Service Appointments
CREATE TABLE IF NOT EXISTS serviceappointment (
    appointment_id      INT             PRIMARY KEY,
    employee_id         INT,
    vin                 VARCHAR(17),
    status              VARCHAR(20),
    appointment_date    DATE,
    FOREIGN KEY (employee_id)   REFERENCES employee(employee_id),
    FOREIGN KEY (vin)           REFERENCES car(vin)
);

-- 1.7 Service Records
CREATE TABLE IF NOT EXISTS servicerecord (
    vin             VARCHAR(17),
    service_id      INT             PRIMARY KEY,
    cost            DECIMAL(10, 2),
    date            DATE,
    service_done    VARCHAR(100),
    employee_id     INT,
    FOREIGN KEY (vin)           REFERENCES car(vin),
    FOREIGN KEY (employee_id)   REFERENCES employee(employee_id)
);


-- ============================================================