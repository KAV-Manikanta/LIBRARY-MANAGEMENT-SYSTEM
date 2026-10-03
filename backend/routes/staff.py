from flask import Blueprint, request, jsonify
from backend.db import get_session
from backend.models import Staff, Transaction

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/api/staff', methods=['GET'])
def get_staff_members():
    session = get_session()
    try:
        staff_members = session.query(Staff).all()
        return jsonify({"success": True, "staff": [s.to_dict() for s in staff_members]}), 200
    finally:
        session.close()

@staff_bp.route('/api/staff', methods=['POST'])
def add_staff():
    session = get_session()
    try:
        data = request.get_json() or {}
        name = data.get('Name', '').strip()
        role = data.get('Role', '').strip()
        shift = data.get('Shift_Timing', '').strip()
        password = str(data.get('Password', 'staff123')).strip() or 'staff123'

        if not name or not role or not shift:
            return jsonify({"success": False, "error": "All staff fields (Name, Role, Shift_Timing) are required"}), 400

        staff = Staff(Name=name, Role=role, Shift_Timing=shift, Password=password)
        session.add(staff)
        session.commit()
        return jsonify({"success": True, "staff": staff.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@staff_bp.route('/api/staff/<int:staff_id>', methods=['PUT'])
def update_staff(staff_id):
    session = get_session()
    try:
        data = request.get_json() or {}
        staff = session.query(Staff).filter_by(Staff_ID=staff_id).first()
        if not staff:
            return jsonify({"success": False, "error": "Staff member not found"}), 404

        if 'Name' in data and data['Name'].strip():
            staff.Name = data['Name'].strip()
        if 'Role' in data and data['Role'].strip():
            staff.Role = data['Role'].strip()
        if 'Shift_Timing' in data and data['Shift_Timing'].strip():
            staff.Shift_Timing = data['Shift_Timing'].strip()
        if 'Password' in data and data['Password'].strip():
            pwd = data['Password'].strip()
            if len(pwd) < 4:
                return jsonify({"success": False, "error": "Password must be at least 4 characters"}), 400
            staff.Password = pwd

        session.commit()
        return jsonify({"success": True, "staff": staff.to_dict()}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@staff_bp.route('/api/staff/<int:staff_id>', methods=['DELETE'])
def delete_staff(staff_id):
    session = get_session()
    try:
        staff = session.query(Staff).filter_by(Staff_ID=staff_id).first()
        if not staff:
            return jsonify({"success": False, "error": "Staff member not found"}), 404

        handled_transactions = session.query(Transaction).filter_by(Staff_ID=staff_id).count()
        if handled_transactions > 0:
            return jsonify({
                "success": False, 
                "error": f"Cannot delete staff '{staff.Name}': Authorized {handled_transactions} circulation transactions (Referential Integrity RESTRICT)."
            }), 409

        session.delete(staff)
        session.commit()
        return jsonify({"success": True, "message": "Staff member removed"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()
