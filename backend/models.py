from datetime import date
from sqlalchemy import (
    Column, Integer, String, Date, Numeric, ForeignKey, Table, CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ----------------------------------------------------------------------------
# Associative Table: BOOK_AUTHOR (Many-to-Many between BOOK and AUTHOR)
# ----------------------------------------------------------------------------
book_author = Table(
    'BOOK_AUTHOR',
    Base.metadata,
    Column('Book_ID', Integer, ForeignKey('BOOK.Book_ID', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    Column('Author_ID', Integer, ForeignKey('AUTHOR.Author_ID', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
)

# ----------------------------------------------------------------------------
# Master Entity: PUBLISHER
# ----------------------------------------------------------------------------
class Publisher(Base):
    __tablename__ = 'PUBLISHER'

    Publisher_ID = Column(Integer, primary_key=True, autoincrement=True)
    Publisher_Name = Column(String(100), nullable=False, unique=True)
    Contact_Number = Column(String(15), nullable=False)
    City = Column(String(50), nullable=False)

    books = relationship("Book", back_populates="publisher", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "Publisher_ID": self.Publisher_ID,
            "Publisher_Name": self.Publisher_Name,
            "Contact_Number": self.Contact_Number,
            "City": self.City,
            "Book_Count": len(self.books) if self.books else 0
        }

# ----------------------------------------------------------------------------
# Master Entity: AUTHOR
# ----------------------------------------------------------------------------
class Author(Base):
    __tablename__ = 'AUTHOR'

    Author_ID = Column(Integer, primary_key=True, autoincrement=True)
    First_Name = Column(String(50), nullable=False)
    Last_Name = Column(String(50), nullable=False)
    Nationality = Column(String(50), nullable=False)

    books = relationship("Book", secondary=book_author, back_populates="authors")

    def to_dict(self):
        return {
            "Author_ID": self.Author_ID,
            "First_Name": self.First_Name,
            "Last_Name": self.Last_Name,
            "Full_Name": f"{self.First_Name} {self.Last_Name}",
            "Nationality": self.Nationality,
            "Book_Count": len(self.books) if self.books else 0
        }

# ----------------------------------------------------------------------------
# Master Entity: BOOK
# ----------------------------------------------------------------------------
class Book(Base):
    __tablename__ = 'BOOK'

    Book_ID = Column(Integer, primary_key=True, autoincrement=True)
    Title = Column(String(150), nullable=False)
    Genre = Column(String(50), nullable=False)
    Publication_Year = Column(Integer, nullable=False)
    Total_Copies = Column(Integer, nullable=False)
    Available_Copies = Column(Integer, nullable=False)
    Publisher_ID = Column(Integer, ForeignKey('PUBLISHER.Publisher_ID', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)

    __table_args__ = (
        CheckConstraint('Publication_Year >= 1900', name='chk_pub_year'),
        CheckConstraint('Total_Copies >= 0', name='chk_total_copies'),
        CheckConstraint('Available_Copies >= 0', name='chk_avail_copies'),
        CheckConstraint('Available_Copies <= Total_Copies', name='chk_stock_logic'),
    )

    publisher = relationship("Publisher", back_populates="books")
    authors = relationship("Author", secondary=book_author, back_populates="books")
    transactions = relationship("Transaction", back_populates="book")

    def to_dict(self):
        return {
            "Book_ID": self.Book_ID,
            "Title": self.Title,
            "Genre": self.Genre,
            "Publication_Year": self.Publication_Year,
            "Total_Copies": self.Total_Copies,
            "Available_Copies": self.Available_Copies,
            "Publisher_ID": self.Publisher_ID,
            "Publisher_Name": self.publisher.Publisher_Name if self.publisher else None,
            "Authors": [
                {
                    "Author_ID": a.Author_ID,
                    "Name": f"{a.First_Name} {a.Last_Name}",
                    "Nationality": a.Nationality
                } for a in self.authors
            ],
            "Stock_Status": "Out of Stock" if self.Available_Copies == 0 else ("Low Stock" if self.Available_Copies <= 2 else "In Stock")
        }

# ----------------------------------------------------------------------------
# Master Entity: MEMBER (Patrons / Students)
# ----------------------------------------------------------------------------
class Member(Base):
    __tablename__ = 'MEMBER'

    Member_ID = Column(Integer, primary_key=True, autoincrement=True)
    Full_Name = Column(String(100), nullable=False)
    Email_Address = Column(String(100), nullable=False, unique=True)
    Password = Column(String(255), nullable=True, default='student123')
    Membership_Date = Column(Date, nullable=False, default=date.today)
    Max_Books_Allowed = Column(Integer, nullable=False, default=3)

    __table_args__ = (
        CheckConstraint('Max_Books_Allowed > 0', name='chk_max_books'),
    )

    transactions = relationship("Transaction", back_populates="member")

    def to_dict(self):
        active_loans = sum(1 for t in self.transactions if t.Return_Date is None)
        total_fines = sum(float(t.Fine_Amount or 0.0) for t in self.transactions)
        
        return {
            "Member_ID": self.Member_ID,
            "Full_Name": self.Full_Name,
            "Email_Address": self.Email_Address,
            "Membership_Date": self.Membership_Date.strftime("%Y-%m-%d") if self.Membership_Date else None,
            "Max_Books_Allowed": self.Max_Books_Allowed,
            "Active_Loans_Count": active_loans,
            "Remaining_Quota": max(0, self.Max_Books_Allowed - active_loans),
            "Quota_Exceeded": active_loans >= self.Max_Books_Allowed,
            "Total_Fines_Incurred": total_fines
        }

# ----------------------------------------------------------------------------
# Master Entity: STAFF
# ----------------------------------------------------------------------------
class Staff(Base):
    __tablename__ = 'STAFF'

    Staff_ID = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(100), nullable=False)
    Role = Column(String(50), nullable=False)
    Shift_Timing = Column(String(30), nullable=False)
    Password = Column(String(255), nullable=True, default='staff123')

    transactions = relationship("Transaction", back_populates="staff")

    def to_dict(self):
        return {
            "Staff_ID": self.Staff_ID,
            "Name": self.Name,
            "Role": self.Role,
            "Shift_Timing": self.Shift_Timing,
            "Transactions_Handled": len(self.transactions) if self.transactions else 0
        }

# ----------------------------------------------------------------------------
# Transactional Entity: TRANSACTION (Circulation loans & fines)
# ----------------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = 'TRANSACTION'

    Transaction_ID = Column(Integer, primary_key=True, autoincrement=True)
    Book_ID = Column(Integer, ForeignKey('BOOK.Book_ID', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    Member_ID = Column(Integer, ForeignKey('MEMBER.Member_ID', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    Staff_ID = Column(Integer, ForeignKey('STAFF.Staff_ID', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    Issue_Date = Column(Date, nullable=False, default=date.today)
    Due_Date = Column(Date, nullable=False)
    Return_Date = Column(Date, nullable=True)
    Fine_Amount = Column(Numeric(8, 2), nullable=False, default=0.00)

    __table_args__ = (
        CheckConstraint('Due_Date >= Issue_Date', name='chk_trans_dates'),
        CheckConstraint('Fine_Amount >= 0.00', name='chk_fine_amount'),
    )

    book = relationship("Book", back_populates="transactions")
    member = relationship("Member", back_populates="transactions")
    staff = relationship("Staff", back_populates="transactions")

    def to_dict(self):
        today = date.today()
        is_returned = self.Return_Date is not None
        
        # Calculate dynamic overdue days and potential fine if unreturned
        if not is_returned:
            days_overdue = (today - self.Due_Date).days if today > self.Due_Date else 0
            computed_fine = float(days_overdue * 5.00) if days_overdue > 0 else 0.00
            status = "Overdue" if days_overdue > 0 else "Active"
        else:
            days_overdue = (self.Return_Date - self.Due_Date).days if self.Return_Date > self.Due_Date else 0
            computed_fine = float(self.Fine_Amount or 0.00)
            status = "Returned (Late)" if days_overdue > 0 else "Returned (On Time)"

        return {
            "Transaction_ID": self.Transaction_ID,
            "Book_ID": self.Book_ID,
            "Book_Title": self.book.Title if self.book else "Unknown",
            "Member_ID": self.Member_ID,
            "Member_Name": self.member.Full_Name if self.member else "Unknown",
            "Member_Email": self.member.Email_Address if self.member else "",
            "Staff_ID": self.Staff_ID,
            "Staff_Name": self.staff.Name if self.staff else "Unknown",
            "Issue_Date": self.Issue_Date.strftime("%Y-%m-%d") if self.Issue_Date else None,
            "Due_Date": self.Due_Date.strftime("%Y-%m-%d") if self.Due_Date else None,
            "Return_Date": self.Return_Date.strftime("%Y-%m-%d") if self.Return_Date else None,
            "Fine_Amount": float(self.Fine_Amount or 0.00),
            "Computed_Fine": computed_fine,
            "Days_Overdue": days_overdue,
            "Status": status
        }
