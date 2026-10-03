-- ============================================================================
-- ACADEMIC LIBRARY MANAGEMENT SYSTEM - SAMPLE DATASET (SEED DATA)
-- Based on DBMS Capstone Project Report (Aditya University)
-- ============================================================================

USE library_management_db;

-- ----------------------------------------------------------------------------
-- 1. Insert Publishers
-- ----------------------------------------------------------------------------
INSERT INTO PUBLISHER (Publisher_ID, Publisher_Name, Contact_Number, City) VALUES
(1, 'Pearson Education', '022-26543210', 'Mumbai'),
(2, 'McGraw-Hill Education', '011-45678901', 'New Delhi'),
(3, 'MIT Press', '080-34567890', 'Bengaluru'),
(4, 'O''Reilly Media', '044-89012345', 'Chennai'),
(5, 'Oxford University Press', '040-67890123', 'Hyderabad');

-- ----------------------------------------------------------------------------
-- 2. Insert Authors
-- ----------------------------------------------------------------------------
INSERT INTO AUTHOR (Author_ID, First_Name, Last_Name, Nationality) VALUES
(1, 'Abraham', 'Silberschatz', 'American'),
(2, 'Peter', 'Galvin', 'American'),
(3, 'Stuart', 'Russell', 'British'),
(4, 'Peter', 'Norvig', 'American'),
(5, 'Thomas', 'Cormen', 'American'),
(6, 'Ian', 'Goodfellow', 'Canadian');

-- ----------------------------------------------------------------------------
-- 3. Insert Books
-- Note: Available_Copies reflects initial physical state prior to seed transactions
-- ----------------------------------------------------------------------------
INSERT INTO BOOK (Book_ID, Title, Genre, Publication_Year, Total_Copies, Available_Copies, Publisher_ID) VALUES
(1, 'Database System Concepts', 'Computer Science', 2019, 10, 8, 2),
(2, 'Artificial Intelligence: A Modern Approach', 'Artificial Intelligence', 2020, 8, 6, 1),
(3, 'Introduction to Algorithms', 'Algorithms', 2022, 12, 10, 3),
(4, 'Operating System Concepts', 'Computer Science', 2018, 6, 5, 2),
(5, 'Computer Networks', 'Networking', 2021, 5, 4, 1),
(6, 'Designing Data-Intensive Applications', 'Database Systems', 2017, 7, 7, 4),
(7, 'Deep Learning', 'Artificial Intelligence', 2016, 6, 5, 3);

-- ----------------------------------------------------------------------------
-- 4. Insert Multi-Author Associations (BOOK_AUTHOR)
-- ----------------------------------------------------------------------------
INSERT INTO BOOK_AUTHOR (Book_ID, Author_ID) VALUES
(1, 1), -- Database System Concepts -> Silberschatz
(2, 3), -- AI: Modern Approach -> Russell
(2, 4), -- AI: Modern Approach -> Norvig
(3, 5), -- Intro to Algorithms -> Cormen
(4, 1), -- OS Concepts -> Silberschatz
(4, 2), -- OS Concepts -> Galvin
(7, 6); -- Deep Learning -> Goodfellow

-- ----------------------------------------------------------------------------
-- 5. Insert Members (Students & Project Team Patrons)
-- ----------------------------------------------------------------------------
INSERT INTO MEMBER (Member_ID, Full_Name, Email_Address, Membership_Date, Max_Books_Allowed) VALUES
(1, 'B Vyas Sri Nandan', 'vyas.25ai@aditya.ac.in', '2025-08-01', 5),
(2, 'M Ravi Teja', 'ravi.25ai@aditya.ac.in', '2025-08-01', 5),
(3, 'Ch Karthikeyan', 'karthi.25ai@aditya.ac.in', '2025-08-01', 5),
(4, 'K A V Manikanta', 'mani.25ai@aditya.ac.in', '2025-08-01', 5),
(5, 'Sita Kumari', 'sita.25cs@aditya.ac.in', '2025-09-10', 3),
(6, 'Praveen Kumar', 'prav.25ec@aditya.ac.in', '2025-09-12', 3);

-- ----------------------------------------------------------------------------
-- 6. Insert Staff Members
-- ----------------------------------------------------------------------------
INSERT INTO STAFF (Staff_ID, Name, Role, Shift_Timing) VALUES
(1, 'Suresh Babu', 'Chief Librarian', 'Morning (08:00 - 16:00)'),
(2, 'Lakshmi Prasanna', 'Assistant Librarian', 'Evening (12:00 - 20:00)'),
(3, 'K. Ramanaji', 'Circulation Officer', 'Morning (08:00 - 16:00)');

-- ----------------------------------------------------------------------------
-- 7. Insert Circulation Transactions
-- ----------------------------------------------------------------------------
INSERT INTO TRANSACTION (Transaction_ID, Book_ID, Member_ID, Staff_ID, Issue_Date, Due_Date, Return_Date, Fine_Amount) VALUES
(1, 1, 1, 2, '2026-08-01', '2026-08-15', '2026-08-14', 0.00),
(2, 1, 2, 2, '2026-08-10', '2026-08-24', '2026-08-31', 35.00),
(3, 2, 3, 3, '2026-09-01', '2026-09-15', NULL, 65.00),
(4, 3, 4, 2, '2026-09-15', '2026-09-29', NULL, 0.00),
(5, 2, 1, 1, '2026-09-10', '2026-09-24', NULL, 20.00),
(6, 4, 5, 2, '2026-09-18', '2026-10-02', NULL, 0.00),
(7, 5, 6, 3, '2026-09-19', '2026-10-03', NULL, 0.00);
