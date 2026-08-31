-- ============================================================
--  Dealership Database  --  MySQL Workbench
--  Tables: dealerships, customers, employee, car,
--          transactions, serviceappointment, servicerecord
-- ============================================================

-- ============================================================
-- SECTION 1: CREATE SCHEMA & TABLES
-- ============================================================

CREATE DATABASE IF NOT EXISTS dealership_db;
USE dealership_db;

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
-- SECTION 2: BASIC SELECT QUERIES
-- ============================================================

-- 2.1  All dealerships
SELECT * FROM dealerships;

-- 2.2  All cars currently available in inventory
SELECT vin, brand, model, year, type, miles, listing_price
FROM   car
WHERE  inventory_status = 'Available'
ORDER  BY listing_price;

-- 2.3  All customers with an active loan
SELECT customer_id, name, credit_score, loan
FROM   customers
WHERE  loan > 0
ORDER  BY loan DESC;

-- 2.4  All employees and their dealership location
SELECT e.employee_id, e.name, e.position,
       d.city, d.state
FROM   employee  e
JOIN   dealerships d ON e.dealership_id = d.dealership_id
ORDER  BY d.city, e.position;

-- 2.5  All completed service appointments
SELECT sa.appointment_id, sa.appointment_date,
       sa.vin, e.name AS technician
FROM   serviceappointment sa
JOIN   employee e ON sa.employee_id = e.employee_id
WHERE  sa.status = 'Completed'
ORDER  BY sa.appointment_date;


-- ============================================================
-- SECTION 3: FILTERING & SORTING
-- ============================================================

-- 3.1  Cars newer than 2020 with fewer than 40,000 miles
SELECT vin, brand, model, year, miles, listing_price
FROM   car
WHERE  year > 2020
  AND  miles < 40000
ORDER  BY year DESC, miles;

-- 3.2  Customers with credit score >= 700
SELECT customer_id, name, credit_score, email
FROM   customers
WHERE  credit_score >= 700
ORDER  BY credit_score DESC;

-- 3.3  Transactions in a given date range  (adjust dates as needed)
SELECT sale_id, date, vin, sold_price
FROM   transactions
WHERE  date BETWEEN '2025-01-01' AND '2025-06-30'
ORDER  BY date;

-- 3.4  Service records with cost above $200
SELECT sr.service_id, sr.vin, sr.service_done,
       sr.cost, sr.date, e.name AS technician
FROM   servicerecord sr
JOIN   employee e ON sr.employee_id = e.employee_id
WHERE  sr.cost > 200
ORDER  BY sr.cost DESC;

-- 3.5  Cars by a specific brand  (change 'Honda' as needed)
SELECT vin, model, year, miles, listing_price, inventory_status
FROM   car
WHERE  brand = 'Honda'
ORDER  BY year DESC;


-- ============================================================
-- SECTION 4: AGGREGATE / SUMMARY QUERIES
-- ============================================================

-- 4.1  Total sales revenue per dealership
SELECT d.dealership_id, d.city, d.state,
       COUNT(t.sale_id)       AS total_sales,
       SUM(t.sold_price)      AS total_revenue,
       AVG(t.sold_price)      AS avg_sale_price
FROM   dealerships d
JOIN   employee    e  ON e.dealership_id = d.dealership_id
JOIN   transactions t ON t.employee_id  = e.employee_id
GROUP  BY d.dealership_id, d.city, d.state
ORDER  BY total_revenue DESC;

-- 4.2  Number of cars in inventory by brand
SELECT brand,
       COUNT(*)                                         AS total_cars,
       SUM(inventory_status = 'Available')              AS available,
       SUM(inventory_status = 'Sold')                   AS sold
FROM   car
GROUP  BY brand
ORDER  BY total_cars DESC;

-- 4.3  Top 5 best-selling employees
SELECT e.employee_id, e.name, e.position,
       COUNT(t.sale_id)   AS cars_sold,
       SUM(t.sold_price)  AS total_revenue
FROM   employee     e
JOIN   transactions t ON t.employee_id = e.employee_id
GROUP  BY e.employee_id, e.name, e.position
ORDER  BY cars_sold DESC
LIMIT  5;

-- 4.4  Average credit score of customers who bought a car
SELECT AVG(c.credit_score) AS avg_credit_score
FROM   customers   c
JOIN   transactions t ON t.customer_id = c.customer_id;

-- 4.5  Total service revenue per employee
SELECT e.employee_id, e.name,
       COUNT(sr.service_id)  AS services_done,
       SUM(sr.cost)          AS total_service_revenue
FROM   employee     e
JOIN   servicerecord sr ON sr.employee_id = e.employee_id
GROUP  BY e.employee_id, e.name
ORDER  BY total_service_revenue DESC;

-- 4.6  Most common service type performed
SELECT service_done,
       COUNT(*)       AS times_performed,
       AVG(cost)      AS avg_cost
FROM   servicerecord
GROUP  BY service_done
ORDER  BY times_performed DESC;

-- 4.7  Inventory value still on the lot
SELECT d.city,
       COUNT(c.vin)            AS cars_on_lot,
       SUM(c.listing_price)    AS total_listing_value,
       SUM(c.bought_price)     AS total_cost_basis
FROM   car c
JOIN   dealerships d ON c.dealership = d.dealership_id
WHERE  c.inventory_status = 'Available'
GROUP  BY d.city;


-- ============================================================
-- SECTION 5: JOIN QUERIES
-- ============================================================

-- 5.1  Full transaction details (customer + employee + car)
SELECT t.sale_id,
       t.date,
       c.name                          AS customer,
       c.credit_score,
       e.name                          AS salesperson,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       t.sold_price,
       (t.sold_price - ca.bought_price) AS profit
FROM   transactions t
JOIN   customers    c  ON t.customer_id = c.customer_id
JOIN   employee     e  ON t.employee_id = e.employee_id
JOIN   car          ca ON t.vin         = ca.vin
ORDER  BY t.date DESC;

-- 5.2  Service appointment with full car and technician info
SELECT sa.appointment_id,
       sa.appointment_date,
       sa.status,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       ca.miles,
       e.name                          AS technician,
       d.city                          AS dealership_city
FROM   serviceappointment sa
JOIN   car         ca ON sa.vin         = ca.vin
JOIN   employee    e  ON sa.employee_id = e.employee_id
JOIN   dealerships d  ON e.dealership_id = d.dealership_id
ORDER  BY sa.appointment_date DESC;

-- 5.3  Customers and all cars they have purchased
SELECT c.customer_id, c.name, c.credit_score,
       GROUP_CONCAT(
           CONCAT(ca.year, ' ', ca.brand, ' ', ca.model)
           ORDER BY t.date
           SEPARATOR ' | '
       ) AS cars_purchased
FROM   customers   c
JOIN   transactions t  ON t.customer_id = c.customer_id
JOIN   car         ca  ON t.vin         = ca.vin
GROUP  BY c.customer_id, c.name, c.credit_score;

-- 5.4  Cars that have BOTH been sold AND have a service record
SELECT ca.vin,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       t.sold_price,
       t.date                  AS sale_date,
       sr.service_done,
       sr.cost                 AS service_cost,
       sr.date                 AS service_date
FROM   car          ca
JOIN   transactions t  ON t.vin        = ca.vin
JOIN   servicerecord sr ON sr.vin      = ca.vin
ORDER  BY ca.vin;


-- ============================================================
-- SECTION 6: SUBQUERIES
-- ============================================================

-- 6.1  Cars priced above the average listing price
SELECT vin, brand, model, year, listing_price
FROM   car
WHERE  listing_price > (SELECT AVG(listing_price) FROM car)
ORDER  BY listing_price DESC;

-- 6.2  Customers who have spent more than the average transaction amount
SELECT c.customer_id, c.name,
       SUM(t.sold_price)  AS total_spent
FROM   customers   c
JOIN   transactions t ON t.customer_id = c.customer_id
GROUP  BY c.customer_id, c.name
HAVING total_spent > (SELECT AVG(sold_price) FROM transactions);

-- 6.3  Employees who have never made a sale
SELECT employee_id, name, position
FROM   employee
WHERE  employee_id NOT IN (
    SELECT DISTINCT employee_id FROM transactions
);

-- 6.4  Most expensive car sold at each dealership
SELECT d.city,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       t.sold_price
FROM   transactions t
JOIN   car          ca ON t.vin          = ca.vin
JOIN   employee     e  ON t.employee_id  = e.employee_id
JOIN   dealerships  d  ON e.dealership_id = d.dealership_id
WHERE  t.sold_price = (
    SELECT MAX(t2.sold_price)
    FROM   transactions t2
    JOIN   employee     e2 ON t2.employee_id   = e2.employee_id
    WHERE  e2.dealership_id = e.dealership_id
)
ORDER  BY t.sold_price DESC;


-- ============================================================
-- SECTION 7: USEFUL VIEWS
-- ============================================================

-- 7.1  Sales summary view
CREATE OR REPLACE VIEW vw_sales_summary AS
SELECT t.sale_id,
       t.date,
       c.name                           AS customer,
       e.name                           AS salesperson,
       d.city                           AS dealership,
       CONCAT(ca.year,' ',ca.brand,' ',ca.model) AS car,
       t.sold_price,
       ca.bought_price,
       (t.sold_price - ca.bought_price) AS gross_profit
FROM   transactions t
JOIN   customers   c  ON t.customer_id  = c.customer_id
JOIN   employee    e  ON t.employee_id  = e.employee_id
JOIN   car         ca ON t.vin          = ca.vin
JOIN   dealerships d  ON e.dealership_id = d.dealership_id;

-- Usage: SELECT * FROM vw_sales_summary;

-- 7.2  Current inventory view
CREATE OR REPLACE VIEW vw_inventory AS
SELECT ca.vin, ca.brand, ca.model, ca.year, ca.type,
       ca.miles, ca.listing_price, ca.inventory_status,
       d.city AS dealership_city
FROM   car ca
JOIN   dealerships d ON ca.dealership = d.dealership_id
WHERE  ca.inventory_status = 'Available';

-- Usage: SELECT * FROM vw_inventory;

-- 7.3  Service history view
CREATE OR REPLACE VIEW vw_service_history AS
SELECT sr.service_id, sr.date,
       CONCAT(ca.year,' ',ca.brand,' ',ca.model) AS car,
       sr.vin, sr.service_done, sr.cost,
       e.name AS technician, d.city AS dealership
FROM   servicerecord sr
JOIN   car         ca ON sr.vin         = ca.vin
JOIN   employee    e  ON sr.employee_id = e.employee_id
JOIN   dealerships d  ON e.dealership_id = d.dealership_id;

-- Usage: SELECT * FROM vw_service_history;
