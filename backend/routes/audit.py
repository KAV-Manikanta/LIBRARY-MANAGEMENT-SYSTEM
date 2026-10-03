from datetime import date
from flask import Blueprint, jsonify, request
from sqlalchemy import func
from backend.db import get_session, is_mysql
from backend.models import Transaction, Book, Member, Staff, Publisher, Author
from backend.config import Config

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/api/fines/overdue', methods=['GET'])
def get_overdue_loans():
    """Retrieve all open loans past their due date with dynamic penalty computation."""
    session = get_session()
    try:
        today = date.today()
        # Active loans where Due_Date < today
        overdue_loans = session.query(Transaction).filter(
            Transaction.Return_Date.is_(None),
            Transaction.Due_Date < today
        ).all()

        results = []
        fine_rate = Config.FINE_PER_DAY

        for t in overdue_loans:
            days_late = (today - t.Due_Date).days
            accrued_fine = round(days_late * fine_rate, 2)
            results.append({
                "Transaction_ID": t.Transaction_ID,
                "Book_ID": t.Book_ID,
                "Book_Title": t.book.Title if t.book else "Unknown",
                "Member_ID": t.Member_ID,
                "Member_Name": t.member.Full_Name if t.member else "Unknown",
                "Member_Email": t.member.Email_Address if t.member else "",
                "Staff_Name": t.staff.Name if t.staff else "Unknown",
                "Issue_Date": t.Issue_Date.strftime("%Y-%m-%d"),
                "Due_Date": t.Due_Date.strftime("%Y-%m-%d"),
                "Days_Overdue": days_late,
                "Daily_Rate": fine_rate,
                "Accrued_Penalty": accrued_fine
            })

        return jsonify({
            "success": True,
            "count": len(results),
            "overdue_loans": results,
            "total_accrued_penalties": sum(r["Accrued_Penalty"] for r in results)
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@audit_bp.route('/api/fines/summary', methods=['GET'])
def get_fine_summary():
    """Comprehensive fine audit metrics."""
    session = get_session()
    try:
        today = date.today()
        all_tx = session.query(Transaction).all()

        total_collected = sum(float(t.Fine_Amount or 0.0) for t in all_tx if t.Return_Date is not None)
        
        # Pending penalties from active overdue loans
        pending_penalties = 0.0
        active_overdue_count = 0
        for t in all_tx:
            if t.Return_Date is None and today > t.Due_Date:
                active_overdue_count += 1
                days = (today - t.Due_Date).days
                pending_penalties += (days * Config.FINE_PER_DAY)

        fines_with_values = [float(t.Fine_Amount) for t in all_tx if t.Fine_Amount and t.Fine_Amount > 0]
        avg_fine = sum(fines_with_values) / len(fines_with_values) if fines_with_values else 0.0

        return jsonify({
            "success": True,
            "total_collected_fines": round(total_collected, 2),
            "total_pending_penalties": round(pending_penalties, 2),
            "active_overdue_loans_count": active_overdue_count,
            "average_assessed_fine": round(avg_fine, 2),
            "fine_rate_per_day": Config.FINE_PER_DAY
        }), 200
    finally:
        session.close()


@audit_bp.route('/api/fines/member-summary', methods=['GET'])
def get_member_fine_summary():
    """Simulates V_MemberFineSummary view."""
    session = get_session()
    try:
        members = session.query(Member).all()
        summary = []
        for m in members:
            total_loans = len(m.transactions)
            active_loans = sum(1 for t in m.transactions if t.Return_Date is None)
            total_fines = sum(float(t.Fine_Amount or 0.0) for t in m.transactions)
            
            # calculate active overdue penalty
            active_pending = 0.0
            today = date.today()
            for t in m.transactions:
                if t.Return_Date is None and today > t.Due_Date:
                    active_pending += (today - t.Due_Date).days * Config.FINE_PER_DAY

            summary.append({
                "Member_ID": m.Member_ID,
                "Full_Name": m.Full_Name,
                "Email_Address": m.Email_Address,
                "Total_Loans": total_loans,
                "Active_Loans": active_loans,
                "Settled_Fines": round(total_fines, 2),
                "Pending_Fines": round(active_pending, 2),
                "Total_Liability": round(total_fines + active_pending, 2)
            })

        return jsonify({"success": True, "member_fines": summary}), 200
    finally:
        session.close()


@audit_bp.route('/api/analytics/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    """Aggregated metrics for top-level system KPI cards."""
    session = get_session()
    try:
        today = date.today()
        total_books = session.query(Book).count()
        total_copies = session.query(func.sum(Book.Total_Copies)).scalar() or 0
        avail_copies = session.query(func.sum(Book.Available_Copies)).scalar() or 0
        total_members = session.query(Member).count()
        total_staff = session.query(Staff).count()
        total_publishers = session.query(Publisher).count()
        total_authors = session.query(Author).count()

        active_loans = session.query(Transaction).filter(Transaction.Return_Date.is_(None)).count()
        overdue_loans = session.query(Transaction).filter(
            Transaction.Return_Date.is_(None),
            Transaction.Due_Date < today
        ).count()

        total_fines = session.query(func.sum(Transaction.Fine_Amount)).scalar() or 0.0

        return jsonify({
            "success": True,
            "database_engine": "MySQL 8.0" if is_mysql else "SQLite (Fallback)",
            "stats": {
                "total_titles": total_books,
                "total_inventory_copies": int(total_copies),
                "available_copies": int(avail_copies),
                "checked_out_copies": int(total_copies - avail_copies),
                "total_members": total_members,
                "total_staff": total_staff,
                "total_publishers": total_publishers,
                "total_authors": total_authors,
                "active_loans": active_loans,
                "overdue_loans": overdue_loans,
                "total_fines_collected": float(total_fines)
            }
        }), 200
    finally:
        session.close()


@audit_bp.route('/api/fines/settle', methods=['POST'])
def settle_fine():
    """Administrative action: Mark fine as collected/settled."""
    session = get_session()
    try:
        data = request.get_json() or {}
        transaction_id = int(data.get('Transaction_ID', 0))
        amount_paid = float(data.get('Amount_Paid', 0.0))

        trans = session.query(Transaction).filter_by(Transaction_ID=transaction_id).first()
        if not trans:
            return jsonify({"success": False, "error": "Transaction not found"}), 404

        current_fine = float(trans.Fine_Amount or 0.0)
        new_fine = max(0.0, round(current_fine - amount_paid, 2))
        trans.Fine_Amount = new_fine
        session.commit()

        return jsonify({
            "success": True, 
            "message": f"Payment of ₹{amount_paid:.2f} logged. Outstanding fine: ₹{new_fine:.2f}",
            "remaining_fine": new_fine
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()
