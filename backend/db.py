import logging
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from backend.config import Config
from backend.models import Base, Publisher, Author, Book, Member, Staff, Transaction, book_author

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = None
_SessionFactory = None
is_mysql = False

def init_db_engine():
    global engine, _SessionFactory, is_mysql
    
    if _SessionFactory is not None:
        return engine

    # Try connecting to MySQL 8.0 first (skip localhost on Vercel/serverless)
    import os
    is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    should_try_mysql = not (is_serverless and Config.DB_HOST in ["localhost", "127.0.0.1"])

    if should_try_mysql:
        try:
            mysql_engine = create_engine(
                Config.MYSQL_DATABASE_URI,
                pool_recycle=3600,
                pool_pre_ping=True
            )
            with mysql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("[Database] Successfully connected to MySQL 8.0 at %s:%s/%s", 
                        Config.DB_HOST, Config.DB_PORT, Config.DB_NAME)
            engine = mysql_engine
            is_mysql = True
        except Exception as e:
            logger.warning("[Database] Could not connect to MySQL 8.0 (%s). Initializing SQLite fallback for zero-downtime demonstration.", str(e))
            engine = create_engine(Config.SQLITE_DATABASE_URI, connect_args={"check_same_thread": False})
            is_mysql = False
    else:
        logger.info("[Database] Running in serverless environment. Initializing high-speed SQLite database.")
        engine = create_engine(Config.SQLITE_DATABASE_URI, connect_args={"check_same_thread": False})
        is_mysql = False

    # Bind session factory
    _SessionFactory = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

    # Create tables if not present
    Base.metadata.create_all(bind=engine)
    
    # Ensure Member and Staff tables have Password column for existing installations
    try:
        with engine.connect() as conn:
            if is_mysql:
                check_sql = text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='MEMBER' AND COLUMN_NAME='Password'")
                res = conn.execute(check_sql).fetchone()
                if not res:
                    conn.execute(text("ALTER TABLE MEMBER ADD COLUMN Password VARCHAR(255) DEFAULT 'student123'"))
                    conn.commit()

                check_staff_sql = text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='STAFF' AND COLUMN_NAME='Password'")
                staff_res = conn.execute(check_staff_sql).fetchone()
                if not staff_res:
                    conn.execute(text("ALTER TABLE STAFF ADD COLUMN Password VARCHAR(255) DEFAULT 'staff123'"))
                    conn.commit()
            else:
                pragma_res = conn.execute(text("PRAGMA table_info(MEMBER)")).fetchall()
                col_names = [col[1] for col in pragma_res]
                if 'Password' not in col_names and len(col_names) > 0:
                    conn.execute(text("ALTER TABLE MEMBER ADD COLUMN Password VARCHAR(255) DEFAULT 'student123'"))
                    conn.commit()

                pragma_staff = conn.execute(text("PRAGMA table_info(STAFF)")).fetchall()
                staff_col_names = [col[1] for col in pragma_staff]
                if 'Password' not in staff_col_names and len(staff_col_names) > 0:
                    conn.execute(text("ALTER TABLE STAFF ADD COLUMN Password VARCHAR(255) DEFAULT 'staff123'"))
                    conn.commit()
    except Exception as mig_err:
        logger.warning("[Database] Auto-migration check: %s", str(mig_err))

    # Seed data if database is empty
    seed_initial_data()
    return engine

def get_session():
    """Returns a new active session from the scoped session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        init_db_engine()
    return _SessionFactory()

def seed_initial_data():
    """Populates academic sample data from the DBMS Capstone Project if empty"""
    session = get_session()
    try:
        # Check if books already exist
        if session.query(Book).count() > 0:
            return
        
        logger.info("[Database] Seeding initial academic catalog dataset...")

        # 1. Publishers
        p1 = Publisher(Publisher_Name='Pearson Education', Contact_Number='022-26543210', City='Mumbai')
        p2 = Publisher(Publisher_Name='McGraw-Hill Education', Contact_Number='011-45678901', City='New Delhi')
        p3 = Publisher(Publisher_Name='MIT Press', Contact_Number='080-34567890', City='Bengaluru')
        p4 = Publisher(Publisher_Name='O\'Reilly Media', Contact_Number='044-89012345', City='Chennai')
        p5 = Publisher(Publisher_Name='Oxford University Press', Contact_Number='040-67890123', City='Hyderabad')
        session.add_all([p1, p2, p3, p4, p5])
        session.commit()

        # 2. Authors
        a1 = Author(First_Name='Abraham', Last_Name='Silberschatz', Nationality='American')
        a2 = Author(First_Name='Peter', Last_Name='Galvin', Nationality='American')
        a3 = Author(First_Name='Stuart', Last_Name='Russell', Nationality='British')
        a4 = Author(First_Name='Peter', Last_Name='Norvig', Nationality='American')
        a5 = Author(First_Name='Thomas', Last_Name='Cormen', Nationality='American')
        a6 = Author(First_Name='Ian', Last_Name='Goodfellow', Nationality='Canadian')
        session.add_all([a1, a2, a3, a4, a5, a6])
        session.commit()

        # 3. Books
        b1 = Book(Title='Database System Concepts', Genre='Computer Science', Publication_Year=2019, Total_Copies=10, Available_Copies=8, Publisher_ID=p2.Publisher_ID)
        b2 = Book(Title='Artificial Intelligence: A Modern Approach', Genre='Artificial Intelligence', Publication_Year=2020, Total_Copies=8, Available_Copies=6, Publisher_ID=p1.Publisher_ID)
        b3 = Book(Title='Introduction to Algorithms', Genre='Algorithms', Publication_Year=2022, Total_Copies=12, Available_Copies=10, Publisher_ID=p3.Publisher_ID)
        b4 = Book(Title='Operating System Concepts', Genre='Computer Science', Publication_Year=2018, Total_Copies=6, Available_Copies=5, Publisher_ID=p2.Publisher_ID)
        b5 = Book(Title='Computer Networks', Genre='Networking', Publication_Year=2021, Total_Copies=5, Available_Copies=4, Publisher_ID=p1.Publisher_ID)
        b6 = Book(Title='Designing Data-Intensive Applications', Genre='Database Systems', Publication_Year=2017, Total_Copies=7, Available_Copies=7, Publisher_ID=p4.Publisher_ID)
        b7 = Book(Title='Deep Learning', Genre='Artificial Intelligence', Publication_Year=2016, Total_Copies=6, Available_Copies=5, Publisher_ID=p3.Publisher_ID)
        
        # Author associations
        b1.authors = [a1]
        b2.authors = [a3, a4]
        b3.authors = [a5]
        b4.authors = [a1, a2]
        b7.authors = [a6]

        session.add_all([b1, b2, b3, b4, b5, b6, b7])
        session.commit()

        # 4. Members (Aditya University Capstone Team & Students)
        m1 = Member(Full_Name='B Vyas Sri Nandan', Email_Address='vyas.25ai@aditya.ac.in', Membership_Date=date(2025, 8, 1), Max_Books_Allowed=5)
        m2 = Member(Full_Name='M Ravi Teja', Email_Address='ravi.25ai@aditya.ac.in', Membership_Date=date(2025, 8, 1), Max_Books_Allowed=5)
        m3 = Member(Full_Name='Ch Karthikeyan', Email_Address='karthi.25ai@aditya.ac.in', Membership_Date=date(2025, 8, 1), Max_Books_Allowed=5)
        m4 = Member(Full_Name='K A V Manikanta', Email_Address='mani.25ai@aditya.ac.in', Membership_Date=date(2025, 8, 1), Max_Books_Allowed=5)
        m5 = Member(Full_Name='Sita Kumari', Email_Address='sita.25cs@aditya.ac.in', Membership_Date=date(2025, 9, 10), Max_Books_Allowed=3)
        m6 = Member(Full_Name='Praveen Kumar', Email_Address='prav.25ec@aditya.ac.in', Membership_Date=date(2025, 9, 12), Max_Books_Allowed=3)
        session.add_all([m1, m2, m3, m4, m5, m6])
        session.commit()

        # 5. Staff
        s1 = Staff(Name='Suresh Babu', Role='Chief Librarian', Shift_Timing='Morning (08:00 - 16:00)')
        s2 = Staff(Name='Lakshmi Prasanna', Role='Assistant Librarian', Shift_Timing='Evening (12:00 - 20:00)')
        s3 = Staff(Name='K. Ramanaji', Role='Circulation Officer', Shift_Timing='Morning (08:00 - 16:00)')
        session.add_all([s1, s2, s3])
        session.commit()

        # 6. Transactions (historical and active loans)
        t1 = Transaction(Book_ID=b1.Book_ID, Member_ID=m1.Member_ID, Staff_ID=s2.Staff_ID,
                         Issue_Date=date(2026, 8, 1), Due_Date=date(2026, 8, 15), Return_Date=date(2026, 8, 14), Fine_Amount=0.00)
        t2 = Transaction(Book_ID=b1.Book_ID, Member_ID=m2.Member_ID, Staff_ID=s2.Staff_ID,
                         Issue_Date=date(2026, 8, 10), Due_Date=date(2026, 8, 24), Return_Date=date(2026, 8, 31), Fine_Amount=35.00)
        t3 = Transaction(Book_ID=b2.Book_ID, Member_ID=m3.Member_ID, Staff_ID=s3.Staff_ID,
                         Issue_Date=date(2026, 9, 1), Due_Date=date(2026, 9, 15), Return_Date=None, Fine_Amount=65.00)
        t4 = Transaction(Book_ID=b3.Book_ID, Member_ID=m4.Member_ID, Staff_ID=s2.Staff_ID,
                         Issue_Date=date(2026, 9, 15), Due_Date=date(2026, 9, 29), Return_Date=None, Fine_Amount=0.00)
        t5 = Transaction(Book_ID=b2.Book_ID, Member_ID=m1.Member_ID, Staff_ID=s1.Staff_ID,
                         Issue_Date=date(2026, 9, 10), Due_Date=date(2026, 9, 24), Return_Date=None, Fine_Amount=20.00)
        t6 = Transaction(Book_ID=b4.Book_ID, Member_ID=m5.Member_ID, Staff_ID=s2.Staff_ID,
                         Issue_Date=date(2026, 9, 18), Due_Date=date(2026, 10, 2), Return_Date=None, Fine_Amount=0.00)
        t7 = Transaction(Book_ID=b5.Book_ID, Member_ID=m6.Member_ID, Staff_ID=s3.Staff_ID,
                         Issue_Date=date(2026, 9, 19), Due_Date=date(2026, 10, 3), Return_Date=None, Fine_Amount=0.00)
        
        session.add_all([t1, t2, t3, t4, t5, t6, t7])
        session.commit()
        logger.info("[Database] Academic seed dataset populated successfully.")
    except Exception as e:
        session.rollback()
        logger.error("[Database] Error while seeding data: %s", str(e))
    finally:
        session.close()
