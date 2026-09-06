-- Report-only SQL for the canonical schema.sql definitions.
-- Select DB_NAME first, for example: mysql -D cardealership < dealership_queries.sql
-- Initialize using python manage.py init-db. This file does not create or migrate tables.

-- SECTION 2: BASIC SELECT QUERIES
-- ============================================================

-- 2.1  All dealerships
SELECT * FROM Dealership;

-- 2.2  All cars currently available in inventory
SELECT vin, brand, model, year, type, miles, ListingPrice
FROM Vehicle
WHERE  InventoryStatus = 'Available'
ORDER  BY ListingPrice;

-- 2.3  All customers with an active loan
SELECT CustomerID, CustomerName, CreditScore, loan
FROM Customer
WHERE  loan > 0
ORDER  BY loan DESC;

-- 2.4  All employees and their dealership location
SELECT e.EmployeeID, e.EmployeeName, e.position,
       d.city, d.state
FROM Employee  e
JOIN Dealership d ON e.DealershipID = d.DealershipID
ORDER  BY d.city, e.position;

-- 2.5  All completed service appointments
SELECT sa.AppointmentID, sa.AppointmentDate,
       sa.vin, e.EmployeeName AS technician
FROM ServiceAppointment sa
JOIN Employee e ON sa.EmployeeID = e.EmployeeID
WHERE  sa.status = 'Completed'
ORDER  BY sa.AppointmentDate;


-- ============================================================
-- SECTION 3: FILTERING & SORTING
-- ============================================================

-- 3.1  Cars newer than 2020 with fewer than 40,000 miles
SELECT vin, brand, model, year, miles, ListingPrice
FROM Vehicle
WHERE  year > 2020
  AND  miles < 40000
ORDER  BY year DESC, miles;

-- 3.2  Customers with credit score >= 700
SELECT CustomerID, CustomerName, CreditScore, email
FROM Customer
WHERE  CreditScore >= 700
ORDER  BY CreditScore DESC;

-- 3.3  Transactions in a given SaleDate range  (adjust dates as needed)
SELECT SaleID, SaleDate, vin, SoldPrice
FROM SaleTransaction
WHERE  SaleDate BETWEEN '2025-01-01' AND '2025-06-30'
ORDER  BY SaleDate;

-- 3.4  Service records with cost above $200
SELECT sr.ServiceID, sr.vin, sr.ServiceDone,
       sr.cost, sr.ServiceDate, e.EmployeeName AS technician
FROM ServiceRecord sr
JOIN Employee e ON sr.EmployeeID = e.EmployeeID
WHERE  sr.cost > 200
ORDER  BY sr.cost DESC;

-- 3.5  Cars by a specific brand  (change 'Honda' as needed)
SELECT vin, model, year, miles, ListingPrice, InventoryStatus
FROM Vehicle
WHERE  brand = 'Honda'
ORDER  BY year DESC;


-- ============================================================
-- SECTION 4: AGGREGATE / SUMMARY QUERIES
-- ============================================================

-- 4.1  Total sales revenue per dealership
SELECT d.DealershipID, d.city, d.state,
       COUNT(t.SaleID)       AS total_sales,
       SUM(t.SoldPrice)      AS total_revenue,
       AVG(t.SoldPrice)      AS avg_sale_price
FROM Dealership d
JOIN Employee    e  ON e.DealershipID = d.DealershipID
JOIN SaleTransaction t ON t.EmployeeID  = e.EmployeeID
GROUP  BY d.DealershipID, d.city, d.state
ORDER  BY total_revenue DESC;

-- 4.2  Number of cars in inventory by brand
SELECT brand,
       COUNT(*)                                         AS total_cars,
       SUM(InventoryStatus = 'Available')              AS available,
       SUM(InventoryStatus = 'Sold')                   AS sold
FROM Vehicle
GROUP  BY brand
ORDER  BY total_cars DESC;

-- 4.3  Top 5 best-selling employees
SELECT e.EmployeeID, e.EmployeeName, e.position,
       COUNT(t.SaleID)   AS cars_sold,
       SUM(t.SoldPrice)  AS total_revenue
FROM Employee     e
JOIN SaleTransaction t ON t.EmployeeID = e.EmployeeID
GROUP  BY e.EmployeeID, e.EmployeeName, e.position
ORDER  BY cars_sold DESC
LIMIT  5;

-- 4.4 Average credit score, each purchasing customer counted once
SELECT AVG(c.CreditScore) AS avg_credit_score
FROM Customer c
WHERE EXISTS (SELECT 1 FROM SaleTransaction t WHERE t.CustomerID=c.CustomerID);

-- 4.5  Total service revenue per employee
SELECT e.EmployeeID, e.EmployeeName,
       COUNT(sr.ServiceID)  AS services_done,
       SUM(sr.cost)          AS total_service_revenue
FROM Employee     e
JOIN ServiceRecord sr ON sr.EmployeeID = e.EmployeeID
GROUP  BY e.EmployeeID, e.EmployeeName
ORDER  BY total_service_revenue DESC;

-- 4.6  Most common service type performed
SELECT ServiceDone,
       COUNT(*)       AS times_performed,
       AVG(cost)      AS avg_cost
FROM ServiceRecord
GROUP  BY ServiceDone
ORDER  BY times_performed DESC;

-- 4.7  Inventory value still on the lot
SELECT d.DealershipID, d.city,
       COUNT(c.vin)            AS cars_on_lot,
       SUM(c.ListingPrice)    AS total_listing_value,
       SUM(c.BoughtPrice)     AS total_cost_basis
FROM Vehicle c
JOIN Dealership d ON c.DealershipID = d.DealershipID
WHERE  c.InventoryStatus = 'Available'
GROUP BY d.DealershipID, d.city;


-- ============================================================
-- SECTION 5: JOIN QUERIES
-- ============================================================

-- 5.1  Full transaction details (customer + employee + car)
SELECT t.SaleID,
       t.SaleDate,
       c.CustomerName                          AS customer,
       c.CreditScore,
       e.EmployeeName                          AS salesperson,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       t.SoldPrice,
       (t.SoldPrice - ca.BoughtPrice) AS profit
FROM SaleTransaction t
JOIN Customer    c  ON t.CustomerID = c.CustomerID
JOIN Employee     e  ON t.EmployeeID = e.EmployeeID
JOIN Vehicle          ca ON t.vin         = ca.vin
ORDER  BY t.SaleDate DESC;

-- 5.2  Service appointment with full car and technician info
SELECT sa.AppointmentID,
       sa.AppointmentDate,
       sa.status,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       ca.miles,
       e.EmployeeName                          AS technician,
       d.city                          AS dealership_city
FROM ServiceAppointment sa
JOIN Vehicle         ca ON sa.vin         = ca.vin
JOIN Employee    e  ON sa.EmployeeID = e.EmployeeID
JOIN Dealership d  ON e.DealershipID = d.DealershipID
ORDER  BY sa.AppointmentDate DESC;

-- 5.3  Customers and all cars they have purchased
SELECT c.CustomerID, c.CustomerName, c.CreditScore,
       GROUP_CONCAT(
           CONCAT(ca.year, ' ', ca.brand, ' ', ca.model)
           ORDER BY t.SaleDate
           SEPARATOR ' | '
       ) AS cars_purchased
FROM Customer   c
JOIN SaleTransaction t  ON t.CustomerID = c.CustomerID
JOIN Vehicle         ca  ON t.vin         = ca.vin
GROUP  BY c.CustomerID, c.CustomerName, c.CreditScore;

-- 5.4  Cars that have BOTH been sold AND have a service record
SELECT ca.vin,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       t.SoldPrice,
       t.SaleDate                  AS sale_date,
       sr.ServiceDone,
       sr.cost                 AS service_cost,
       sr.ServiceDate                 AS service_date
FROM Vehicle          ca
JOIN SaleTransaction t  ON t.vin        = ca.vin
JOIN ServiceRecord sr ON sr.vin      = ca.vin
ORDER  BY ca.vin;


-- ============================================================
-- SECTION 6: SUBQUERIES
-- ============================================================

-- 6.1  Cars priced above the average listing price
SELECT vin, brand, model, year, ListingPrice
FROM Vehicle
WHERE  ListingPrice > (SELECT AVG(ListingPrice) FROM Vehicle)
ORDER  BY ListingPrice DESC;

-- 6.2  Customers who have spent more than the average transaction amount
SELECT c.CustomerID, c.CustomerName,
       SUM(t.SoldPrice)  AS total_spent
FROM Customer   c
JOIN SaleTransaction t ON t.CustomerID = c.CustomerID
GROUP  BY c.CustomerID, c.CustomerName
HAVING total_spent > (SELECT AVG(SoldPrice) FROM SaleTransaction);

-- 6.3 Employees who have never made a sale, including nullable legacy assignments
SELECT e.EmployeeID, e.EmployeeName, e.Position
FROM Employee e
WHERE NOT EXISTS (SELECT 1 FROM SaleTransaction t WHERE t.EmployeeID=e.EmployeeID);

-- 6.4  Most expensive car sold at each dealership
SELECT d.city,
       CONCAT(ca.year, ' ', ca.brand, ' ', ca.model) AS car,
       t.SoldPrice
FROM SaleTransaction t
JOIN Vehicle          ca ON t.vin          = ca.vin
JOIN Employee     e  ON t.EmployeeID  = e.EmployeeID
JOIN Dealership  d  ON e.DealershipID = d.DealershipID
WHERE  t.SoldPrice = (
    SELECT MAX(t2.SoldPrice)
    FROM SaleTransaction t2
    JOIN Employee     e2 ON t2.EmployeeID   = e2.EmployeeID
    WHERE  e2.DealershipID = e.DealershipID
)
ORDER  BY t.SoldPrice DESC;


-- ============================================================
-- SECTION 7: USEFUL VIEWS
-- ============================================================

-- 7.1  Sales summary view
CREATE OR REPLACE VIEW vw_sales_summary AS
SELECT t.SaleID,
       t.SaleDate,
       c.CustomerName                           AS customer,
       e.EmployeeName                           AS salesperson,
       d.city                           AS dealership,
       CONCAT(ca.year,' ',ca.brand,' ',ca.model) AS car,
       t.SoldPrice,
       ca.BoughtPrice,
       (t.SoldPrice - ca.BoughtPrice) AS gross_profit
FROM SaleTransaction t
JOIN Customer   c  ON t.CustomerID  = c.CustomerID
JOIN Employee    e  ON t.EmployeeID  = e.EmployeeID
JOIN Vehicle         ca ON t.vin          = ca.vin
JOIN Dealership d  ON e.DealershipID = d.DealershipID;

-- Usage: SELECT * FROM vw_sales_summary;

-- 7.2  Current inventory view
CREATE OR REPLACE VIEW vw_inventory AS
SELECT ca.vin, ca.brand, ca.model, ca.year, ca.type,
       ca.miles, ca.ListingPrice, ca.InventoryStatus,
       d.city AS dealership_city
FROM Vehicle ca
JOIN Dealership d ON ca.DealershipID = d.DealershipID
WHERE  ca.InventoryStatus = 'Available';

-- Usage: SELECT * FROM vw_inventory;

-- 7.3  Service history view
CREATE OR REPLACE VIEW vw_service_history AS
SELECT sr.ServiceID, sr.ServiceDate,
       CONCAT(ca.year,' ',ca.brand,' ',ca.model) AS car,
       sr.vin, sr.ServiceDone, sr.cost,
       e.EmployeeName AS technician, d.city AS dealership
FROM ServiceRecord sr
JOIN Vehicle         ca ON sr.vin         = ca.vin
JOIN Employee    e  ON sr.EmployeeID = e.EmployeeID
JOIN Dealership d  ON e.DealershipID = d.DealershipID;

-- Usage: SELECT * FROM vw_service_history;
