from flask import Blueprint, request, jsonify
from backend.db import get_session
from backend.models import Book, Author, Publisher, Transaction

catalog_bp = Blueprint('catalog', __name__)

# ============================================================================
# BOOKS ENDPOINTS (Catalog Management)
# ============================================================================

@catalog_bp.route('/api/books', methods=['GET'])
def get_books():
    """Retrieve all books with multi-author attributions and publisher details."""
    session = get_session()
    try:
        search_query = request.args.get('search', '').strip().lower()
        genre_filter = request.args.get('genre', '').strip()
        stock_filter = request.args.get('stock', '').strip()

        query = session.query(Book)

        books = query.all()
        results = []

        for b in books:
            book_dict = b.to_dict()
            # In-memory or query filtering
            matches_search = True
            if search_query:
                title_match = search_query in b.Title.lower()
                genre_match = search_query in b.Genre.lower()
                pub_match = b.publisher and search_query in b.publisher.Publisher_Name.lower()
                author_match = any(search_query in f"{a.First_Name} {a.Last_Name}".lower() for a in b.authors)
                matches_search = title_match or genre_match or pub_match or author_match

            matches_genre = True
            if genre_filter and genre_filter.lower() != 'all':
                matches_genre = b.Genre.lower() == genre_filter.lower()

            matches_stock = True
            if stock_filter == 'available':
                matches_stock = b.Available_Copies > 0
            elif stock_filter == 'low':
                matches_stock = 0 < b.Available_Copies <= 2
            elif stock_filter == 'out':
                matches_stock = b.Available_Copies == 0

            if matches_search and matches_genre and matches_stock:
                results.append(book_dict)

        return jsonify({
            "success": True,
            "count": len(results),
            "books": results
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@catalog_bp.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    """Retrieve a single book by ID."""
    session = get_session()
    try:
        book = session.query(Book).filter_by(Book_ID=book_id).first()
        if not book:
            return jsonify({"success": False, "error": f"Book ID {book_id} not found"}), 404
        return jsonify({"success": True, "book": book.to_dict()}), 200
    finally:
        session.close()

@catalog_bp.route('/api/books', methods=['POST'])
def create_book():
    """Create a new book with multi-author attributions."""
    session = get_session()
    try:
        data = request.get_json() or {}
        title = data.get('Title', '').strip()
        genre = data.get('Genre', '').strip()
        pub_year = int(data.get('Publication_Year', 2024))
        total_copies = int(data.get('Total_Copies', 1))
        available_copies = int(data.get('Available_Copies', total_copies))
        publisher_id = int(data.get('Publisher_ID', 0))
        author_ids = data.get('Author_IDs', [])

        # Validations (matching DB CHECK constraints)
        if not title:
            return jsonify({"success": False, "error": "Title is required"}), 400
        if not genre:
            return jsonify({"success": False, "error": "Genre is required"}), 400
        if pub_year < 1900:
            return jsonify({"success": False, "error": "Publication Year must be >= 1900"}), 400
        if total_copies < 0 or available_copies < 0:
            return jsonify({"success": False, "error": "Copies cannot be negative"}), 400
        if available_copies > total_copies:
            return jsonify({"success": False, "error": "Available copies cannot exceed total copies"}), 400

        # Validate publisher
        publisher = session.query(Publisher).filter_by(Publisher_ID=publisher_id).first()
        if not publisher:
            return jsonify({"success": False, "error": f"Publisher with ID {publisher_id} does not exist"}), 400

        new_book = Book(
            Title=title,
            Genre=genre,
            Publication_Year=pub_year,
            Total_Copies=total_copies,
            Available_Copies=available_copies,
            Publisher_ID=publisher_id
        )

        # Attach Authors
        if author_ids:
            authors = session.query(Author).filter(Author.Author_ID.in_(author_ids)).all()
            new_book.authors = authors

        session.add(new_book)
        session.commit()

        return jsonify({
            "success": True,
            "message": "Book registered successfully in catalog",
            "book": new_book.to_dict()
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@catalog_bp.route('/api/books/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    """Update an existing book's details."""
    session = get_session()
    try:
        book = session.query(Book).filter_by(Book_ID=book_id).first()
        if not book:
            return jsonify({"success": False, "error": "Book not found"}), 404

        data = request.get_json() or {}
        if 'Title' in data:
            book.Title = data['Title'].strip()
        if 'Genre' in data:
            book.Genre = data['Genre'].strip()
        if 'Publication_Year' in data:
            book.Publication_Year = int(data['Publication_Year'])
        if 'Total_Copies' in data:
            new_total = int(data['Total_Copies'])
            if new_total < book.Available_Copies:
                return jsonify({"success": False, "error": "Total copies cannot be less than current available copies"}), 400
            book.Total_Copies = new_total
        if 'Available_Copies' in data:
            new_avail = int(data['Available_Copies'])
            if new_avail > book.Total_Copies:
                return jsonify({"success": False, "error": "Available copies cannot exceed total copies"}), 400
            book.Available_Copies = new_avail
        if 'Publisher_ID' in data:
            book.Publisher_ID = int(data['Publisher_ID'])
        if 'Author_IDs' in data:
            authors = session.query(Author).filter(Author.Author_ID.in_(data['Author_IDs'])).all()
            book.authors = authors

        session.commit()
        return jsonify({"success": True, "message": "Book updated successfully", "book": book.to_dict()}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@catalog_bp.route('/api/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Delete a book, enforcing foreign key RESTRICT constraint."""
    session = get_session()
    try:
        book = session.query(Book).filter_by(Book_ID=book_id).first()
        if not book:
            return jsonify({"success": False, "error": "Book not found"}), 404

        # Enforce ON DELETE RESTRICT behavior: check active or historical loans
        active_loans = session.query(Transaction).filter_by(Book_ID=book_id).count()
        if active_loans > 0:
            return jsonify({
                "success": False,
                "error": f"Cannot delete book '{book.Title}': {active_loans} circulation transactions reference it (Referential Integrity RESTRICT)."
            }), 409

        session.delete(book)
        session.commit()
        return jsonify({"success": True, "message": "Book removed from catalog"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


# ============================================================================
# AUTHORS ENDPOINTS
# ============================================================================

@catalog_bp.route('/api/authors', methods=['GET'])
def get_authors():
    session = get_session()
    try:
        authors = session.query(Author).all()
        return jsonify({"success": True, "authors": [a.to_dict() for a in authors]}), 200
    finally:
        session.close()

@catalog_bp.route('/api/authors', methods=['POST'])
def create_author():
    session = get_session()
    try:
        data = request.get_json() or {}
        first_name = data.get('First_Name', '').strip()
        last_name = data.get('Last_Name', '').strip()
        nationality = data.get('Nationality', '').strip()

        if not first_name or not last_name or not nationality:
            return jsonify({"success": False, "error": "All author fields are required"}), 400

        author = Author(First_Name=first_name, Last_Name=last_name, Nationality=nationality)
        session.add(author)
        session.commit()
        return jsonify({"success": True, "author": author.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


# ============================================================================
# PUBLISHERS ENDPOINTS
# ============================================================================

@catalog_bp.route('/api/publishers', methods=['GET'])
def get_publishers():
    session = get_session()
    try:
        publishers = session.query(Publisher).all()
        return jsonify({"success": True, "publishers": [p.to_dict() for p in publishers]}), 200
    finally:
        session.close()

@catalog_bp.route('/api/publishers', methods=['POST'])
def create_publisher():
    session = get_session()
    try:
        data = request.get_json() or {}
        pub_name = data.get('Publisher_Name', '').strip()
        contact = data.get('Contact_Number', '').strip()
        city = data.get('City', '').strip()

        if not pub_name or not contact or not city:
            return jsonify({"success": False, "error": "All publisher fields are required"}), 400

        # Check unique constraint
        existing = session.query(Publisher).filter_by(Publisher_Name=pub_name).first()
        if existing:
            return jsonify({"success": False, "error": f"Publisher '{pub_name}' already exists"}), 409

        publisher = Publisher(Publisher_Name=pub_name, Contact_Number=contact, City=city)
        session.add(publisher)
        session.commit()
        return jsonify({"success": True, "publisher": publisher.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()
