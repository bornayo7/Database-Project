-- Canonical MySQL 8.4 schema. Select an EMPTY database first; manage.py init-db checks this.
-- No DROP or implicit migration. All integer entity identifiers are database-generated.
CREATE TABLE SchemaVersion (Version INT PRIMARY KEY) ENGINE=InnoDB;
CREATE TABLE Dealership (
 DealershipID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 Address VARCHAR(255) NOT NULL, City VARCHAR(100) NOT NULL,
 State CHAR(2) NOT NULL, ZipCode VARCHAR(10) NOT NULL,
 CHECK (CHAR_LENGTH(TRIM(Address)) > 0), CHECK (CHAR_LENGTH(TRIM(City)) > 0)
) ENGINE=InnoDB;
CREATE TABLE Customer (
 CustomerID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 CustomerName VARCHAR(100) NOT NULL,
 CreditScore INT NULL COMMENT '300-850, or NULL for legacy records',
 Email VARCHAR(255) NULL, PhoneNumber VARCHAR(20) NULL,
 Loan DECIMAL(10,2) NULL COMMENT 'Positive amount, or NULL for no loan',
 CHECK (CreditScore BETWEEN 300 AND 850), CHECK (Loan > 0),
 CHECK (CHAR_LENGTH(TRIM(CustomerName)) > 0)
) ENGINE=InnoDB;
CREATE TABLE Employee (
 EmployeeID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 EmployeeName VARCHAR(100) NOT NULL, PhoneNumber VARCHAR(20) NULL, Email VARCHAR(255) NULL,
 Position VARCHAR(50) NULL, DealershipID INT NULL,
 FOREIGN KEY (DealershipID) REFERENCES Dealership(DealershipID),
 CHECK (CHAR_LENGTH(TRIM(EmployeeName)) > 0)
) ENGINE=InnoDB;
CREATE TABLE Vehicle (
 VIN VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PRIMARY KEY,
 Model VARCHAR(100) NOT NULL, Type VARCHAR(50) NULL,
 Year INT NULL COMMENT '1886 onward, new forms allow at most next year',
 Brand VARCHAR(100) NULL, DealershipID INT NULL,
 Miles INT NULL COMMENT 'Nonnegative', BoughtPrice DECIMAL(10,2) NULL,
 ListingPrice DECIMAL(10,2) NULL COMMENT 'Required for new vehicles, legacy missing values remain NULL',
 InventoryStatus VARCHAR(20) NOT NULL,
 FOREIGN KEY (DealershipID) REFERENCES Dealership(DealershipID),
 CHECK (CHAR_LENGTH(TRIM(VIN)) > 0), CHECK (CHAR_LENGTH(TRIM(Model)) > 0),
 CHECK (Year BETWEEN 1886 AND 9999), CHECK (Miles >= 0),
 CHECK (BoughtPrice > 0), CHECK (ListingPrice > 0),
 CHECK (InventoryStatus IN ('Available','Sold','Reserved')),
 INDEX idx_vehicle_status (InventoryStatus)
) ENGINE=InnoDB;
CREATE TABLE SaleTransaction (
 SaleID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 SaleDate DATE NOT NULL, CustomerID INT NULL, EmployeeID INT NULL,
 VIN VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL UNIQUE,
 SoldPrice DECIMAL(10,2) NOT NULL,
 RestockStatus VARCHAR(20) NULL COMMENT 'Pre-sale status, NULL legacy reversal requires an explicit choice',
 FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID),
 FOREIGN KEY (EmployeeID) REFERENCES Employee(EmployeeID), FOREIGN KEY (VIN) REFERENCES Vehicle(VIN),
 CHECK (SoldPrice > 0), CHECK (RestockStatus IN ('Available','Reserved')),
 INDEX idx_sale_date (SaleDate,SaleID)
) ENGINE=InnoDB;
CREATE TABLE ServiceRecord (
 ServiceID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 VIN VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
 Cost DECIMAL(10,2) NULL, ServiceDate DATE NULL, ServiceDone VARCHAR(100) NULL, EmployeeID INT NULL,
 FOREIGN KEY (VIN) REFERENCES Vehicle(VIN), FOREIGN KEY (EmployeeID) REFERENCES Employee(EmployeeID),
 CHECK (Cost > 0), INDEX idx_service_date (ServiceDate,ServiceID)
) ENGINE=InnoDB;
CREATE TABLE ServiceAppointment (
 AppointmentID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 EmployeeID INT NULL, CustomerID INT NULL,
 VIN VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
 Status VARCHAR(20) NOT NULL, AppointmentDate DATE NULL, DealershipID INT NULL,
 FOREIGN KEY (EmployeeID) REFERENCES Employee(EmployeeID), FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID),
 FOREIGN KEY (VIN) REFERENCES Vehicle(VIN), FOREIGN KEY (DealershipID) REFERENCES Dealership(DealershipID),
 CHECK (Status IN ('Scheduled','Completed','Cancelled','Delayed')),
 INDEX idx_appointment_date (AppointmentDate,AppointmentID)
) ENGINE=InnoDB;
INSERT INTO SchemaVersion (Version) VALUES (1);
