from datetime import date, timedelta
from flask import Blueprint, request, jsonify
from backend.db import get_session
from backend.models import Transaction, Book, Member, Staff
from backend.config import Config

circulation_bp = Blueprint('circulation', __name__)

@circulation_bp.route('/api/circulation/transactions', methods=['GET'])
def get_transactions():
    """Retrieve all circulation transactions with search and filter capabilities."""
    session = get_session()
    try:
        status_filter = request.args.get('status', 'all').lower()
        search_query = request.args.get('search', '').strip().lower()
        member_id = request.args.get('member_id', type=int)
        book_id = request.args.get('book_id', type=int)

        query = session.query(Transaction).order_by(Transaction.Transaction_ID.desc())

        if member_id:
            query = query.filter(Transaction.Member_ID == member_id)
        if book_id:
            query = query.filter(Transaction.Book_ID == book_id)

        all_tx = query.all()
        results = []
        today = date.today()

        for t in all_tx:
            t_data = t.to_dict()

            # Status filtering
            is_returned = t.Return_Date is not None
            is_overdue = (not is_returned and today > t.Due_Date) or (is_returned and t.Return_Date > t.Due_Date)

            include = True
            if status_filter == 'active':
                include = not is_returned
            elif status_filter == 'returned':
                include = is_returned
            elif status_filter == 'overdue':
                include = is_overdue

            # Search filtering
            if include and search_query:
                include = (
                    search_query in t_data['Book_Title'].lower() or
                    search_query in t_data['Member_Name'].lower() or
                    search_query in t_data['Staff_Name'].lower() or
                    search_query in str(t.Transaction_ID)
                )

            if include:
                results.append(t_data)

        return jsonify({"success": True, "count": len(results), "transactions": results}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

# ============================================================================
# CHECKOUT / ISSUE WORKFLOW (ACID TRANSACTION BLOCK)
# ============================================================================
@circulation_bp.route('/api/circulation/issue', methods=['POST'])
def issue_book():
    """
    ACID-Compliant Book Checkout Workflow:
    1. Validates Member existence and borrowing quota (Max_Books_Allowed).
    2. Locks Book record (FOR UPDATE) to prevent race conditions during concurrent requests.
    3. Verifies Available_Copies > 0.
    4. Automatically decrements Available_Copies (Inventory Synchronization).
    5. Inserts TRANSACTION record with atomic Commit/Rollback.
    """
    session = get_session()
    try:
        data = request.get_json() or {}
        book_id = int(data.get('Book_ID', 0))
        member_id = int(data.get('Member_ID', 0))
        staff_id = int(data.get('Staff_ID', 0))
        duration_days = int(data.get('Duration_Days', Config.DEFAULT_LOAN_DAYS))

        if not book_id or not member_id or not staff_id:
            return jsonify({"success": False, "error": "Book_ID, Member_ID, and Staff_ID are all required"}), 400

        # Start explicit ACID transaction boundary
        session.begin()

        # Step 1: Validate Member & Check Quota Limit
        member = session.query(Member).filter_by(Member_ID=member_id).first()
        if not member:
            session.rollback()
            return jsonify({"success": False, "error": f"Member ID {member_id} does not exist"}), 404

        active_loans = session.query(Transaction).filter(
            Transaction.Member_ID == member_id,
            Transaction.Return_Date.is_(None)
        ).count()

        if active_loans >= member.Max_Books_Allowed:
            session.rollback()
            return jsonify({
                "success": False,
                "error": f"Borrowing Limit Exceeded: Patron '{member.Full_Name}' has {active_loans} active loans (Maximum permitted quota: {member.Max_Books_Allowed})."
            }), 400

        # Step 2: Validate Staff
        staff = session.query(Staff).filter_by(Staff_ID=staff_id).first()
        if not staff:
            session.rollback()
            return jsonify({"success": False, "error": f"Staff ID {staff_id} does not exist"}), 404

        # Step 3: Row Locking on Book to prevent race conditions
        # with_for_update() enforces row-level exclusive lock on MySQL InnoDB
        book = session.query(Book).filter_by(Book_ID=book_id).with_for_update().first()
        if not book:
            session.rollback()
            return jsonify({"success": False, "error": f"Book ID {book_id} not found"}), 404

        if book.Available_Copies <= 0:
            session.rollback()
            return jsonify({
                "success": False,
                "error": f"Copy Out of Stock: '{book.Title}' currently has 0 available copies."
            }), 400

        # Step 4: Inventory Synchronization (Simulating MySQL Trigger trg_after_issue_insert)
        book.Available_Copies -= 1

        # Step 5: Insert TRANSACTION record
        issue_date = date.today()
        due_date = issue_date + timedelta(days=duration_days)

        new_trans = Transaction(
            Book_ID=book_id,
            Member_ID=member_id,
            Staff_ID=staff_id,
            Issue_Date=issue_date,
            Due_Date=due_date,
            Return_Date=None,
            Fine_Amount=0.00
        )
        session.add(new_trans)

        # Atomic commit
        session.commit()

        return jsonify({
            "success": True,
            "message": f"Book '{book.Title}' successfully checked out to {member.Full_Name}.",
            "transaction": new_trans.to_dict(),
            "remaining_stock": book.Available_Copies
        }), 201

    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": f"Transaction aborted (Rolled back): {str(e)}"}), 500
    finally:
        session.close()


# ============================================================================
# CHECK-IN / RETURN WORKFLOW (FINE CALCULATION & INVENTORY RESTORATION)
# ============================================================================
@circulation_bp.route('/api/circulation/return', methods=['POST'])
def return_book():
    """
    ACID-Compliant Book Check-in Workflow:
    1. Fetches active transaction.
    2. Validates Return_Date is NULL.
    3. Calculates overdue fine: Rs 5.00 * (Return_Date - Due_Date) if overdue.
    4. Automatically increments Available_Copies (Inventory Synchronization).
    5. Commits transaction safely.
    """
    session = get_session()
    try:
        data = request.get_json() or {}
        transaction_id = int(data.get('Transaction_ID', 0))
        return_date_str = data.get('Return_Date')

        if not transaction_id:
            return jsonify({"success": False, "error": "Transaction_ID is required"}), 400

        session.begin()

        # Step 1: Fetch transaction with row lock
        trans = session.query(Transaction).filter_by(Transaction_ID=transaction_id).with_for_update().first()
        if not trans:
            session.rollback()
            return jsonify({"success": False, "error": f"Transaction ID {transaction_id} not found"}), 404

        if trans.Return_Date is not None:
            session.rollback()
            return jsonify({
                "success": False,
                "error": f"Book already returned on {trans.Return_Date.strftime('%Y-%m-%d')}."
            }), 400

        # Step 2: Determine return date
        if return_date_str:
            try:
                ret_date = date.fromisoformat(return_date_str)
            except ValueError:
                ret_date = date.today()
        else:
            ret_date = date.today()

        # Enforce check constraint: Return_Date must be >= Issue_Date
        if ret_date < trans.Issue_Date:
            session.rollback()
            return jsonify({"success": False, "error": "Return Date cannot be earlier than Issue Date"}), 400

        # Step 3: Automatic Fine Calculation (Rs 5.00/day late)
        fine_rate = Config.FINE_PER_DAY
        days_late = (ret_date - trans.Due_Date).days if ret_date > trans.Due_Date else 0
        computed_fine = round(days_late * fine_rate, 2) if days_late > 0 else 0.00

        # Step 4: Inventory Synchronization (Simulating MySQL Trigger trg_after_return_update)
        book = session.query(Book).filter_by(Book_ID=trans.Book_ID).with_for_update().first()
        if book:
            if book.Available_Copies < book.Total_Copies:
                book.Available_Copies += 1

        # Step 5: Update Transaction record
        trans.Return_Date = ret_date
        trans.Fine_Amount = computed_fine

        session.commit()

        return jsonify({
            "success": True,
            "message": f"Book '{trans.book.Title if trans.book else 'Book'}' successfully returned.",
            "transaction_id": trans.Transaction_ID,
            "return_date": ret_date.strftime("%Y-%m-%d"),
            "days_overdue": days_late,
            "fine_amount": computed_fine,
            "available_copies_now": book.Available_Copies if book else None
        }), 200

    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": f"Return transaction failed (Rolled back): {str(e)}"}), 500
    finally:
        session.close()
