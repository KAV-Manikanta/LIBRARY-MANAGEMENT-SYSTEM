-- ============================================================================
-- ACADEMIC LIBRARY MANAGEMENT SYSTEM - QUERIES & ANALYTICAL DQL
-- Based on DBMS Capstone Project Report (Review - I & II)
-- ============================================================================

USE library_management_db;

-- Q1: Retrieve all members eligible to borrow up to 5 books
SELECT Member_ID, Full_Name, Email_Address, Max_Books_Allowed 
FROM MEMBER 
WHERE Max_Books_Allowed = 5;

-- Q2: List books where available stock is 5 or fewer (Low Stock Alert)
SELECT Book_ID, Title, Genre, Available_Copies, Total_Copies 
FROM BOOK 
WHERE Available_Copies <= 5;

-- Q3: Display all distinct literary genres in the catalog
SELECT DISTINCT Genre FROM BOOK ORDER BY Genre;

-- Q4: List active open book loans (not yet returned)
SELECT Transaction_ID, Book_ID, Member_ID, Issue_Date, Due_Date 
FROM TRANSACTION 
WHERE Return_Date IS NULL;

-- Q5: Inner Join: Retrieve books along with their publisher names
SELECT b.Book_ID, b.Title, p.Publisher_Name, b.Genre, b.Publication_Year
FROM BOOK b 
INNER JOIN PUBLISHER p ON b.Publisher_ID = p.Publisher_ID;

-- Q6: Equi Join: List members alongside the titles of books they borrowed
SELECT m.Full_Name, b.Title, t.Issue_Date, t.Due_Date, t.Return_Date
FROM MEMBER m, TRANSACTION t, BOOK b 
WHERE m.Member_ID = t.Member_ID AND b.Book_ID = t.Book_ID;

-- Q7: Left Outer Join: Show all books and any active transactions
SELECT b.Title, t.Transaction_ID, t.Issue_Date, t.Return_Date 
FROM BOOK b 
LEFT JOIN TRANSACTION t ON b.Book_ID = t.Book_ID;

-- Q8: Right Outer Join: Show all staff members and transactions authorized by them
SELECT s.Name AS Staff_Name, s.Role, t.Transaction_ID, t.Issue_Date 
FROM TRANSACTION t 
RIGHT JOIN STAFF s ON t.Staff_ID = s.Staff_ID;

-- Q9: Multi-Author Attribution Join
SELECT 
    b.Book_ID,
    b.Title,
    GROUP_CONCAT(CONCAT(a.First_Name, ' ', a.Last_Name) SEPARATOR ', ') AS Authors,
    p.Publisher_Name,
    b.Available_Copies,
    b.Total_Copies
FROM BOOK b
LEFT JOIN BOOK_AUTHOR ba ON b.Book_ID = ba.Book_ID
LEFT JOIN AUTHOR a ON ba.Author_ID = a.Author_ID
LEFT JOIN PUBLISHER p ON b.Publisher_ID = p.Publisher_ID
GROUP BY b.Book_ID, b.Title, p.Publisher_Name, b.Available_Copies, b.Total_Copies;

-- Q10: Count total titles published by each publisher
SELECT p.Publisher_Name, COUNT(b.Book_ID) AS Total_Books 
FROM PUBLISHER p 
LEFT JOIN BOOK b ON p.Publisher_ID = b.Publisher_ID 
GROUP BY p.Publisher_Name;

-- Q11: Total fines collected and average fine per loan
SELECT 
    SUM(Fine_Amount) AS Total_Fines_Assessed, 
    AVG(Fine_Amount) AS Avg_Fine 
FROM TRANSACTION 
WHERE Fine_Amount > 0;

-- Q12: Members who have borrowed more than one book
SELECT Member_ID, COUNT(Transaction_ID) AS Total_Borrows 
FROM TRANSACTION 
GROUP BY Member_ID 
HAVING COUNT(Transaction_ID) > 1;

-- Q13: Nested Subquery (IN): Find all members with overdue books
SELECT Full_Name, Email_Address 
FROM MEMBER 
WHERE Member_ID IN (
    SELECT Member_ID 
    FROM TRANSACTION 
    WHERE Return_Date IS NULL AND Due_Date < CURDATE()
);

-- Q14: Correlated Subquery: Books with fewer copies than the average in their genre
SELECT b1.Title, b1.Genre, b1.Available_Copies 
FROM BOOK b1 
WHERE b1.Available_Copies < (
    SELECT AVG(b2.Available_Copies) 
    FROM BOOK b2 
    WHERE b2.Genre = b1.Genre
);
