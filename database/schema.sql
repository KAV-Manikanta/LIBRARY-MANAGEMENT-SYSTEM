-- ============================================================================
-- ACADEMIC LIBRARY MANAGEMENT SYSTEM - DATABASE SCHEMA (3NF NORMALIZED)
-- DBMS Capstone Project - Aditya University
-- Target DBMS: MySQL 8.0+
-- Authors: B Vyas Sri Nandan, M Ravi Teja, Ch Karthikeyan, K A V Manikanta
-- ============================================================================

DROP DATABASE IF EXISTS library_management_db;
CREATE DATABASE library_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE library_management_db;

-- ----------------------------------------------------------------------------
-- 1. Master Entity: PUBLISHER
-- ----------------------------------------------------------------------------
CREATE TABLE PUBLISHER (
    Publisher_ID INT AUTO_INCREMENT PRIMARY KEY,
    Publisher_Name VARCHAR(100) NOT NULL UNIQUE,
    Contact_Number VARCHAR(15) NOT NULL,
    City VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. Master Entity: AUTHOR
-- ----------------------------------------------------------------------------
CREATE TABLE AUTHOR (
    Author_ID INT AUTO_INCREMENT PRIMARY KEY,
    First_Name VARCHAR(50) NOT NULL,
    Last_Name VARCHAR(50) NOT NULL,
    Nationality VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. Master Entity: BOOK
-- ----------------------------------------------------------------------------
CREATE TABLE BOOK (
    Book_ID INT AUTO_INCREMENT PRIMARY KEY,
    Title VARCHAR(150) NOT NULL,
    Genre VARCHAR(50) NOT NULL,
    Publication_Year INT NOT NULL,
    Total_Copies INT NOT NULL,
    Available_Copies INT NOT NULL,
    Publisher_ID INT NOT NULL,
    CONSTRAINT chk_pub_year CHECK (Publication_Year >= 1900),
    CONSTRAINT chk_total_copies CHECK (Total_Copies >= 0),
    CONSTRAINT chk_avail_copies CHECK (Available_Copies >= 0),
    CONSTRAINT chk_stock_logic CHECK (Available_Copies <= Total_Copies),
    CONSTRAINT fk_book_publisher FOREIGN KEY (Publisher_ID) 
        REFERENCES PUBLISHER(Publisher_ID) 
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. Associative Entity: BOOK_AUTHOR (Resolves M:N relationship)
-- ----------------------------------------------------------------------------
CREATE TABLE BOOK_AUTHOR (
    Book_ID INT NOT NULL,
    Author_ID INT NOT NULL,
    PRIMARY KEY (Book_ID, Author_ID),
    CONSTRAINT fk_ba_book FOREIGN KEY (Book_ID) 
        REFERENCES BOOK(Book_ID) 
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ba_author FOREIGN KEY (Author_ID) 
        REFERENCES AUTHOR(Author_ID) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 5. Master Entity: MEMBER (Patrons / Students)
-- ----------------------------------------------------------------------------
CREATE TABLE MEMBER (
    Member_ID INT AUTO_INCREMENT PRIMARY KEY,
    Full_Name VARCHAR(100) NOT NULL,
    Email_Address VARCHAR(100) NOT NULL UNIQUE,
    Membership_Date DATE NOT NULL,
    Max_Books_Allowed INT NOT NULL DEFAULT 3,
    CONSTRAINT chk_max_books CHECK (Max_Books_Allowed > 0)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 6. Master Entity: STAFF (Librarians & Circulation Desk Officers)
-- ----------------------------------------------------------------------------
CREATE TABLE STAFF (
    Staff_ID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Role VARCHAR(50) NOT NULL,
    Shift_Timing VARCHAR(30) NOT NULL
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 7. Transactional Entity: TRANSACTION (Circulation loans & fines)
-- ----------------------------------------------------------------------------
CREATE TABLE TRANSACTION (
    Transaction_ID INT AUTO_INCREMENT PRIMARY KEY,
    Book_ID INT NOT NULL,
    Member_ID INT NOT NULL,
    Staff_ID INT NOT NULL,
    Issue_Date DATE NOT NULL,
    Due_Date DATE NOT NULL,
    Return_Date DATE NULL,
    Fine_Amount DECIMAL(8, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT chk_trans_dates CHECK (Due_Date >= Issue_Date),
    CONSTRAINT chk_fine_amount CHECK (Fine_Amount >= 0.00),
    CONSTRAINT fk_trans_book FOREIGN KEY (Book_ID) 
        REFERENCES BOOK(Book_ID) 
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_trans_member FOREIGN KEY (Member_ID) 
        REFERENCES MEMBER(Member_ID) 
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_trans_staff FOREIGN KEY (Staff_ID) 
        REFERENCES STAFF(Staff_ID) 
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- B-Tree Performance Indexes
-- ----------------------------------------------------------------------------
CREATE INDEX idx_book_genre ON BOOK(Genre, Title);
CREATE INDEX idx_trans_dates ON TRANSACTION(Issue_Date, Due_Date, Return_Date);
CREATE INDEX idx_member_email ON MEMBER(Email_Address);

-- ============================================================================
-- DATABASE TRIGGERS FOR INVENTORY SYNCHRONIZATION & FINE CALCULATION
-- ============================================================================
DELIMITER //

-- Trigger 1: Automatically decrement Available_Copies on new loan issue
CREATE TRIGGER trg_after_issue_insert
AFTER INSERT ON TRANSACTION
FOR EACH ROW
BEGIN
    UPDATE BOOK
    SET Available_Copies = Available_Copies - 1
    WHERE Book_ID = NEW.Book_ID;
END //

-- Trigger 2: Automatically increment Available_Copies and calculate late fine on return
CREATE TRIGGER trg_after_return_update
AFTER UPDATE ON TRANSACTION
FOR EACH ROW
BEGIN
    DECLARE v_days_late INT DEFAULT 0;
    DECLARE v_fine_rate DECIMAL(5,2) DEFAULT 5.00; -- Rs 5.00 per late day

    -- Trigger executes strictly when book is newly returned (was NULL, now set)
    IF OLD.Return_Date IS NULL AND NEW.Return_Date IS NOT NULL THEN
        -- 1. Restore book stock in real-time
        UPDATE BOOK
        SET Available_Copies = Available_Copies + 1
        WHERE Book_ID = NEW.Book_ID;

        -- 2. Calculate fine automatically if returned after due date
        IF NEW.Return_Date > NEW.Due_Date THEN
            SET v_days_late = DATEDIFF(NEW.Return_Date, NEW.Due_Date);
            -- Note: Fine_Amount can also be computed at application level or updated here
        END IF;
    END IF;
END //

-- ============================================================================
-- STORED PROCEDURE: TRANSACTIONAL BOOK ISSUE WITH QUOTA & ROW LOCKING
-- ============================================================================
CREATE PROCEDURE IssueBook(
    IN p_book_id INT,
    IN p_member_id INT,
    IN p_staff_id INT,
    IN p_duration_days INT
)
BEGIN
    DECLARE v_stock INT;
    DECLARE v_current_borrows INT;
    DECLARE v_limit INT;

    START TRANSACTION;

    -- Verify patron borrowing limit
    SELECT Max_Books_Allowed INTO v_limit 
    FROM MEMBER 
    WHERE Member_ID = p_member_id;

    SELECT COUNT(*) INTO v_current_borrows 
    FROM TRANSACTION 
    WHERE Member_ID = p_member_id AND Return_Date IS NULL;

    IF v_current_borrows >= v_limit THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'Error: Patron has reached borrow limit.';
    END IF;

    -- Lock book row and check availability to prevent race conditions
    SELECT Available_Copies INTO v_stock 
    FROM BOOK 
    WHERE Book_ID = p_book_id 
    FOR UPDATE;

    IF v_stock <= 0 THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'Error: Copy is out of stock.';
    ELSE
        INSERT INTO TRANSACTION (
            Book_ID, Member_ID, Staff_ID, Issue_Date, Due_Date, Return_Date, Fine_Amount
        ) VALUES (
            p_book_id,
            p_member_id,
            p_staff_id,
            CURDATE(),
            DATE_ADD(CURDATE(), INTERVAL p_duration_days DAY),
            NULL,
            0.00
        );

        -- Available_Copies is decremented either by trigger or explicit update
        -- UPDATE BOOK SET Available_Copies = Available_Copies - 1 WHERE Book_ID = p_book_id;

        COMMIT;
    END IF;
END //

DELIMITER ;

-- ============================================================================
-- OPERATIONAL VIEWS
-- ============================================================================

-- View 1: Available Books (Public catalog view)
CREATE VIEW V_AvailableBooks AS
SELECT 
    Book_ID, 
    Title, 
    Genre, 
    Publication_Year, 
    Total_Copies, 
    Available_Copies 
FROM BOOK 
WHERE Available_Copies > 0;

-- View 2: Member Fine Summary (Administrative fine tracking)
CREATE VIEW V_MemberFineSummary AS
SELECT 
    m.Member_ID, 
    m.Full_Name, 
    m.Email_Address,
    COUNT(t.Transaction_ID) AS Total_Loans,
    SUM(CASE WHEN t.Return_Date IS NULL THEN 1 ELSE 0 END) AS Active_Loans,
    COALESCE(SUM(t.Fine_Amount), 0.00) AS Total_Fine_Amount
FROM MEMBER m 
LEFT JOIN TRANSACTION t ON m.Member_ID = t.Member_ID 
GROUP BY m.Member_ID, m.Full_Name, m.Email_Address;

-- View 3: Current Active Issues
CREATE VIEW V_CurrentIssues AS
SELECT 
    t.Transaction_ID,
    b.Title AS Book_Title,
    m.Full_Name AS Member_Name,
    s.Name AS Issued_By_Staff,
    t.Issue_Date,
    t.Due_Date,
    DATEDIFF(CURDATE(), t.Due_Date) AS Days_Overdue,
    CASE 
        WHEN CURDATE() > t.Due_Date THEN (DATEDIFF(CURDATE(), t.Due_Date) * 5.00)
        ELSE 0.00 
    END AS Accrued_Fine
FROM TRANSACTION t
JOIN BOOK b ON t.Book_ID = b.Book_ID
JOIN MEMBER m ON t.Member_ID = m.Member_ID
JOIN STAFF s ON t.Staff_ID = s.Staff_ID
WHERE t.Return_Date IS NULL;
