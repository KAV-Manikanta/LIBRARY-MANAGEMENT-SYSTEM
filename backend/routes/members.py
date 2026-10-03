import re
from datetime import date
from flask import Blueprint, request, jsonify
from backend.db import get_session
from backend.models import Member, Transaction

members_bp = Blueprint('members', __name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

@members_bp.route('/api/members', methods=['GET'])
def get_members():
    """Retrieve all library members with dynamic quota and borrowing indicators."""
    session = get_session()
    try:
        search_query = request.args.get('search', '').strip().lower()
        quota_filter = request.args.get('quota_status', '').strip()

        members = session.query(Member).all()
        results = []

        for m in members:
            m_dict = m.to_dict()

            matches_search = True
            if search_query:
                matches_search = (
                    search_query in m.Full_Name.lower() or
                    search_query in m.Email_Address.lower() or
                    search_query in str(m.Member_ID)
                )

            matches_quota = True
            if quota_filter == 'available':
                matches_quota = not m_dict['Quota_Exceeded']
            elif quota_filter == 'full':
                matches_quota = m_dict['Quota_Exceeded']

            if matches_search and matches_quota:
                results.append(m_dict)

        return jsonify({"success": True, "count": len(results), "members": results}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@members_bp.route('/api/members/<int:member_id>', methods=['GET'])
def get_member(member_id):
    """Retrieve member details including active loans and full history."""
    session = get_session()
    try:
        member = session.query(Member).filter_by(Member_ID=member_id).first()
        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        member_data = member.to_dict()
        transactions = session.query(Transaction).filter_by(Member_ID=member_id).order_by(Transaction.Issue_Date.desc()).all()
        member_data["History"] = [t.to_dict() for t in transactions]
        member_data["Active_Loans"] = [t.to_dict() for t in transactions if t.Return_Date is None]

        return jsonify({"success": True, "member": member_data}), 200
    finally:
        session.close()

@members_bp.route('/api/members', methods=['POST'])
def register_member():
    """Register a new student patron with email validation, password, and borrowing quota."""
    session = get_session()
    try:
        data = request.get_json() or {}
        full_name = data.get('Full_Name', '').strip()
        email = data.get('Email_Address', '').strip().lower()
        password = str(data.get('Password') or data.get('password') or 'student123').strip()
        membership_date_str = data.get('Membership_Date')
        max_books = int(data.get('Max_Books_Allowed', 5))

        if not full_name:
            return jsonify({"success": False, "error": "Full Name is required"}), 400
        if not email or not EMAIL_REGEX.match(email):
            return jsonify({
                "success": False, 
                "error": "Invalid email address format. Please use a normal email (e.g. name@gmail.com) or college email (e.g. name@collegename.in)."
            }), 400
        if len(password) < 4:
            return jsonify({"success": False, "error": "Password must be at least 4 characters long"}), 400
        if max_books <= 0:
            return jsonify({"success": False, "error": "Max Books Allowed must be greater than 0"}), 400

        # Check unique email constraint
        existing = session.query(Member).filter_by(Email_Address=email).first()
        if existing:
            return jsonify({
                "success": False, 
                "error": f"A student account with email '{email}' is already registered."
            }), 409

        m_date = date.today()
        if membership_date_str:
            try:
                m_date = date.fromisoformat(membership_date_str)
            except ValueError:
                m_date = date.today()

        new_member = Member(
            Full_Name=full_name,
            Email_Address=email,
            Password=password,
            Membership_Date=m_date,
            Max_Books_Allowed=max_books
        )

        session.add(new_member)
        session.commit()

        return jsonify({
            "success": True,
            "message": "Student account registered successfully",
            "member": new_member.to_dict()
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@members_bp.route('/api/members/bulk', methods=['POST'])
def register_members_bulk():
    """Register multiple student accounts in a single batch with email validation and passwords."""
    session = get_session()
    try:
        data = request.get_json() or {}
        students = data.get('students', [])
        if not students:
            return jsonify({"success": False, "error": "No student records provided"}), 400

        added = []
        skipped = []

        for s in students:
            name = s.get('Full_Name', '').strip()
            email = s.get('Email_Address', '').strip().lower()
            password = str(s.get('Password') or s.get('password') or 'student123').strip()
            max_books = int(s.get('Max_Books_Allowed', 5))

            if not name or not email or not EMAIL_REGEX.match(email):
                skipped.append({"name": name, "email": email, "reason": "Invalid name or email format"})
                continue

            existing = session.query(Member).filter_by(Email_Address=email).first()
            if existing:
                skipped.append({"name": name, "email": email, "reason": "Email already exists"})
                continue

            new_m = Member(
                Full_Name=name,
                Email_Address=email,
                Password=password,
                Membership_Date=date.today(),
                Max_Books_Allowed=max_books
            )
            session.add(new_m)
            added.append(name)

        session.commit()
        return jsonify({
            "success": True,
            "message": f"Successfully registered {len(added)} students.",
            "count_added": len(added),
            "added": added,
            "skipped": skipped
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@members_bp.route('/api/members/<int:member_id>', methods=['PUT'])
def update_member(member_id):
    """Update member profile (name, email, password) or adjust borrowing quota."""
    session = get_session()
    try:
        member = session.query(Member).filter_by(Member_ID=member_id).first()
        if not member:
            return jsonify({"success": False, "error": "Student account not found"}), 404

        data = request.get_json() or {}
        
        # 1. Update Full Name
        if 'Full_Name' in data:
            new_name = data['Full_Name'].strip()
            if not new_name:
                return jsonify({"success": False, "error": "Full Name cannot be empty"}), 400
            member.Full_Name = new_name

        # 2. Update Email Address (Normal or College)
        if 'Email_Address' in data:
            new_email = data['Email_Address'].strip().lower()
            if not EMAIL_REGEX.match(new_email):
                return jsonify({
                    "success": False, 
                    "error": "Invalid email format. Use a normal email (e.g. name@gmail.com) or college email (e.g. name@collegename.in)."
                }), 400
            if new_email != member.Email_Address:
                existing = session.query(Member).filter_by(Email_Address=new_email).first()
                if existing:
                    return jsonify({"success": False, "error": f"Email '{new_email}' is already in use by another account."}), 409
                member.Email_Address = new_email

        # 3. Update Password
        if 'Password' in data and data['Password']:
            new_pass = str(data['Password']).strip()
            if len(new_pass) < 4:
                return jsonify({"success": False, "error": "New password must be at least 4 characters long"}), 400
            member.Password = new_pass

        # 4. Update Max Books Allowed
        if 'Max_Books_Allowed' in data:
            new_quota = int(data['Max_Books_Allowed'])
            if new_quota <= 0:
                return jsonify({"success": False, "error": "Max Books Allowed must be > 0"}), 400
            member.Max_Books_Allowed = new_quota

        session.commit()
        return jsonify({
            "success": True, 
            "message": "Student account details updated successfully", 
            "member": member.to_dict()
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@members_bp.route('/api/members/<int:member_id>', methods=['DELETE'])
def delete_member(member_id):
    """Delete a member, enforcing foreign key RESTRICT constraint."""
    session = get_session()
    try:
        member = session.query(Member).filter_by(Member_ID=member_id).first()
        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Enforce ON DELETE RESTRICT
        active_loans = session.query(Transaction).filter_by(Member_ID=member_id).count()
        if active_loans > 0:
            return jsonify({
                "success": False,
                "error": f"Cannot delete patron '{member.Full_Name}': {active_loans} loan transactions are on file. Active or historical records must be cleared first (Referential Integrity RESTRICT)."
            }), 409

        session.delete(member)
        session.commit()
        return jsonify({"success": True, "message": "Member removed successfully"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()
