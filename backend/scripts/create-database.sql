-- Run this after MySQL server is running.
-- From command line: mysql -u root -p < create-database.sql
-- Or open MySQL Workbench / mysql client and paste:

CREATE DATABASE IF NOT EXISTS realestate_db;
-- Optional: create a dedicated user
-- CREATE USER IF NOT EXISTS 'realestate'@'localhost' IDENTIFIED BY 'yourpassword';
-- GRANT ALL PRIVILEGES ON realestate_db.* TO 'realestate'@'localhost';
-- FLUSH PRIVILEGES;
