import os
import sys

# Ensure backend folder is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from backend.config import Config
from backend.db import init_db_engine, is_mysql
from backend.routes.catalog import catalog_bp
from backend.routes.members import members_bp
from backend.routes.staff import staff_bp
from backend.routes.circulation import circulation_bp
from backend.routes.audit import audit_bp

def create_app():
    # Setup static folder pointing to frontend distribution or static bundle
    static_folder_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    
    app = Flask(__name__, static_folder=static_folder_path, static_url_path='/static')
    app.config.from_object(Config)

    # Enable Cross-Origin Resource Sharing (CORS) for React frontend
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize Database and Tables
    init_db_engine()

    # Register API Blueprints
    app.register_blueprint(catalog_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(circulation_bp)
    app.register_blueprint(audit_bp)

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        from flask import request
        from backend.db import get_session
        from backend.models import Member, Staff
        data = request.get_json() or {}
        role = data.get('role', 'student').lower()
        identifier = str(data.get('identifier', '')).strip().lower()

        session = get_session()
        try:
            if role == 'admin':
                # Enforce admin credentials and password security
                admin_username = str(identifier or '').strip().lower()
                admin_password = str(data.get('password', '')).strip()

                valid_usernames = ['admin', 'administrator', 'admin@library.org']
                if not admin_username or admin_username not in valid_usernames:
                    return jsonify({"success": False, "error": "Invalid administrator username"}), 401

                expected_admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
                if not admin_password:
                    return jsonify({"success": False, "error": "Admin password is required"}), 401

                if admin_password != expected_admin_password:
                    return jsonify({"success": False, "error": "Incorrect password"}), 401

                return jsonify({
                    "success": True,
                    "user": {
                        "role": "admin",
                        "name": "System Administrator",
                        "email": "admin@library.org",
                        "badge": "Admin Access"
                    }
                }), 200

            elif role == 'staff':
                # Find staff by ID or name and enforce password
                staff_identifier = str(identifier or '').strip()
                staff_password = str(data.get('password', '')).strip()

                if not staff_identifier:
                    return jsonify({"success": False, "error": "Please enter your username"}), 400

                staff = None
                if staff_identifier.isdigit():
                    staff = session.query(Staff).filter_by(Staff_ID=int(staff_identifier)).first()
                if not staff:
                    staff = session.query(Staff).filter(Staff.Name.ilike(f"%{staff_identifier}%")).first()

                if not staff:
                    return jsonify({"success": False, "error": f"Staff account '{staff_identifier}' not found"}), 404

                expected_staff_password = getattr(staff, 'Password', None) or 'staff123'
                if not staff_password:
                    return jsonify({"success": False, "error": "Password is required"}), 401

                if staff_password != expected_staff_password:
                    return jsonify({"success": False, "error": "Incorrect password"}), 401

                return jsonify({
                    "success": True,
                    "user": {
                        "role": "staff",
                        "staff_id": staff.Staff_ID,
                        "name": staff.Name,
                        "staff_role": staff.Role,
                        "shift": staff.Shift_Timing,
                        "badge": f"{staff.Role} ({staff.Shift_Timing})"
                    }
                }), 200

            else:
                # Student / Member login
                password = str(data.get('password', '')).strip()
                if not identifier:
                    return jsonify({"success": False, "error": "Please enter your username"}), 400

                member = None
                if identifier.isdigit():
                    member = session.query(Member).filter_by(Member_ID=int(identifier)).first()
                if not member and '@' in identifier:
                    member = session.query(Member).filter(Member.Email_Address.ilike(identifier)).first()
                if not member and identifier:
                    member = session.query(Member).filter(Member.Full_Name.ilike(f"%{identifier}%")).first()

                if not member:
                    return jsonify({"success": False, "error": f"No account found for '{identifier}'"}), 404

                # Validate student password
                expected_password = getattr(member, 'Password', None) or 'student123'
                if not password:
                    return jsonify({"success": False, "error": "Password is required"}), 401

                if password != expected_password:
                    return jsonify({"success": False, "error": "Incorrect password"}), 401

                return jsonify({
                    "success": True,
                    "user": {
                        "role": "student",
                        "member_id": member.Member_ID,
                        "name": member.Full_Name,
                        "email": member.Email_Address,
                        "max_books": member.Max_Books_Allowed,
                        "badge": "Enrolled Student"
                    }
                }), 200
        finally:
            session.close()

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Academic Library Management System API",
            "database_engine": "MySQL 8.0" if is_mysql else "SQLite (Fallback)",
            "version": "1.0.0"
        }), 200

    # Serve Single Page Application Frontend
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # When Vercel rewrites root requests to /api/index, serve the frontend index.html
        if path in ['', 'api/index', 'api/index.py', 'index', 'index.html']:
            for folder in [os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public')), app.static_folder]:
                idx_file = os.path.join(folder, 'index.html')
                if os.path.exists(idx_file):
                    return send_from_directory(folder, 'index.html')

        if path.startswith('api/') or path == 'api':
            return jsonify({"success": False, "error": f"API endpoint '/{path}' not found"}), 404

        for folder in [os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public')), app.static_folder]:
            if path != "" and os.path.exists(os.path.join(folder, path)):
                return send_from_directory(folder, path)
            elif os.path.exists(os.path.join(folder, 'index.html')):
                return send_from_directory(folder, 'index.html')
        else:
            return jsonify({
                "message": "Academic Library Management System REST API is running.",
                "endpoints": {
                    "catalog": "/api/books",
                    "members": "/api/members",
                    "circulation": "/api/circulation/transactions",
                    "audit": "/api/fines/overdue",
                    "stats": "/api/analytics/dashboard-stats"
                }
            })

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print(f"\n=======================================================")
    print(f" Academic Library Management System REST API")
    print(f" Server running at: http://127.0.0.1:{port}")
    print(f" Database Engine:   {'MySQL 8.0' if is_mysql else 'SQLite (Fallback)'}")
    print(f"=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=True)
