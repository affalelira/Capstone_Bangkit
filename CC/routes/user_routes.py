import os
import logging
import bcrypt
import jwt
from flask import Blueprint, request, jsonify, current_app
import mysql.connector
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz

# Create a Blueprint for user routes
user_bp = Blueprint('user', __name__)

# Muat file .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

# Secret key for JWT token generation
SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')

# Token verification decorator
# Enhanced token verification decorator
def verify_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            token = auth_header.split(' ')[1] if len(auth_header.split(' ')) > 1 else None
        
        if not token:
            return jsonify({
                'status': 'fail', 
                'message': 'Token required'
            }), 403
        
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check for active session
            cursor.execute('''
                SELECT * FROM log_kehadiran 
                WHERE user_id = %s AND logout_time IS NULL 
                ORDER BY login_time DESC LIMIT 1
            ''', (payload['user_id'],))
            
            active_session = cursor.fetchone()

            # Allow logout requests to proceed even if session is active
            if active_session and request.endpoint != 'user.logout':
                return jsonify({
                    'status': 'fail', 
                    'message': 'Previous session not closed. Please logout first.'
                }), 403

            cursor.close()
            connection.close()
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'fail', 'message': 'Token has expired'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'status': 'fail', 'message': 'Invalid token'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# Fungsi untuk menghitung status logout berdasarkan waktu logout
def calculate_logout_status(logout_time_str):
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    logout_time = datetime.strptime(logout_time_str, '%Y-%m-%d %H:%M:%S')
    logout_time = logout_time.replace(tzinfo=jakarta_tz)

    # Tentukan batas waktu untuk early, ontime, dan overtime
    cutoff_time_early = logout_time.replace(hour=20, minute=0, second=0, microsecond=0)  # 8 PM
    cutoff_time_ontime = cutoff_time_early + timedelta(hours=1)  # 9 PM
    cutoff_time_lembur = cutoff_time_early + timedelta(hours=2)  # Lembur 1 jam

    # Hitung status logout berdasarkan waktu yang diberikan
    if logout_time < cutoff_time_early:
        status_logout = "early"
        overtime_hours = 0
    elif cutoff_time_early <= logout_time < cutoff_time_ontime:
        status_logout = "ontime"
        overtime_hours = 0
    elif cutoff_time_ontime <= logout_time < cutoff_time_lembur:
        status_logout = "overtime"
        overtime_hours = min((logout_time - cutoff_time_ontime).total_seconds() / 3600, 1)
    else:
        status_logout = "overtime"
        overtime_hours = min((logout_time - cutoff_time_ontime).total_seconds() / 3600, 3)

    return status_logout, overtime_hours

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Login Route
@user_bp.route('/login', methods=['POST'])
def login():
    logger.info("Login endpoint hit")
    data = request.get_json()
    logger.info("Received data: %s", data)

    username = data.get('username')
    password = data.get('password')

    # Validate input
    if not username or not password:
        logger.warning("Username or password missing in the request")
        return jsonify({
            'status': 'fail',
            'message': 'Username and password are required'
        }), 400

    try:
        # Establish database connection
        logger.info("Connecting to the database")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Find user by username
        logger.info("Looking for user: %s", username)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if not user:
            logger.warning("User not found: %s", username)
            return jsonify({
                'status': 'fail',
                'message': 'User not found'
            }), 401

        # Verify password using bcrypt
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.warning("Invalid password for user: %s", username)
            return jsonify({
                'status': 'fail',
                'message': 'Invalid password'
            }), 401

        # Generate JWT token
        token_payload = {
            'user_id': user['user_id'],
            'username': user['username'],
            'role': user['role'],
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')
        logger.info("Token generated for user: %s", username)

        # Close database connection
        cursor.close()
        conn.close()
        logger.info("Database connection closed")

        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'token': token,
                'user': {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'email': user['email'],
                    'fullname': user['fullname'],
                    'role': user['role'],
                    'posisi': user['posisi']
                }
            }
        }), 200

    except Exception as e:
        logger.error("Error during login: %s", str(e), exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@user_bp.route('/checkout', methods=['POST'])
@verify_token
def logout():
    try:
        # Mendapatkan token dari header
        token = request.headers['Authorization'].split(' ')[1]
        
        # Mendekode token untuk mendapatkan user_id
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']

        # Mendapatkan waktu logout dalam zona waktu Asia/Jakarta
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        logout_time = datetime.now(jakarta_tz)
        logout_time_str = logout_time.strftime('%Y-%m-%d %H:%M:%S')

        # Koneksi ke database
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Mencari sesi login aktif yang belum ditutup
        cursor.execute('''
            SELECT log_id FROM log_kehadiran 
            WHERE user_id = %s AND logout_time IS NULL 
            ORDER BY login_time DESC LIMIT 1
        ''', (user_id,))
        
        session = cursor.fetchone()

        if session:
            # Hitung status logout dan overtime menggunakan fungsi calculate_logout_status
            status_logout, overtime_hours = calculate_logout_status(logout_time_str)

            # Update waktu logout, status_logout, dan overtime_hours pada sesi yang aktif
            cursor.execute('''
                UPDATE log_kehadiran 
                SET logout_time = %s, status_logout = %s
                WHERE log_id = %s
            ''', (logout_time_str, status_logout, session['log_id']))
            connection.commit()

            logout_response = {
                'logout_time': logout_time_str,
                'status_logout': status_logout,
                'overtime_hours': overtime_hours
            }
        else:
            # Tidak ada sesi aktif yang ditemukan
            logout_response = {
                'logout_time': logout_time_str,
                'note': 'No active attendance session found'
            }
        
        cursor.close()
        connection.close()

        # Mengembalikan respons sukses
        return jsonify({
            'status': 'success', 
            'message': 'Logout successful',
            'data': logout_response
        }), 200

    except Exception as e:
        # Mengembalikan respons error
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

# Create User Route
@user_bp.route('/', methods=['POST'])
def create_user():
    data = request.get_json()
    
    # Extract and validate user data
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    fullname = data.get('fullname')
    
    # Ensure role is converted to integer
    try:
        role = int(data.get('role', 0))
    except (TypeError, ValueError):
        return jsonify({
            'status': 'fail', 
            'message': 'Invalid role'
        }), 400

    posisi = data.get('posisi')
    nip = data.get('nip')

    # Validate input
    if not all([username, email, password, fullname, role, posisi, nip]):
        return jsonify({
            'status': 'fail', 
            'message': 'All fields are required'
        }), 400

    try:
        # Hash password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Debugging print statements
        print(f"Role type: {type(role)}, Role value: {role}")
        print(f"Posisi type: {type(posisi)}, Posisi value: {posisi}")

        # Prepare user data
        user_data = (username, email, hashed_password, fullname, role, posisi, nip)
        
        try:
            # Insert into users table
            cursor.execute('''
                INSERT INTO users 
                (username, email, password, fullname, role, posisi, nip) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', user_data)
            
            # Get the inserted user ID
            user_id = cursor.lastrowid

            # Automatically add to data_pegawai if role = 2
            if role == 2:
                print(f"Attempting to insert into data_pegawai for user_id: {user_id}")
                try:
                    cursor.execute('''
                        INSERT INTO data_pegawai 
                        (user_id, NIK, TTL, alamat, jenis_kelamin, no_wa, no_rek, agama, posisi)
                        VALUES (%s, NULL, NULL, NULL, NULL, NULL, NULL, NULL, %s)
                    ''', (user_id, posisi))
                    print(f"Successfully inserted into data_pegawai: {cursor.rowcount} rows")
                except mysql.connector.Error as pegawai_err:
                    print(f"Error inserting into data_pegawai: {pegawai_err}")
                    # You might want to handle this error more specifically

            # Commit the transaction
            conn.commit()

            return jsonify({
                'status': 'success',
                'message': 'User and data_pegawai created successfully',
                'user': {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'fullname': fullname,
                    'role': role,
                    'posisi': posisi,
                    'nip': nip
                }
            }), 201

        except mysql.connector.Error as err:
            # Handle database errors
            conn.rollback()
            print(f"Database error: {err}")
            return jsonify({
                'status': 'fail', 
                'message': str(err)
            }), 400

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500
    finally:
        # Ensure cursor and connection are closed
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Get All Users Route
@user_bp.route('/', methods=['GET'])
def get_all_users():
    try:
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch all users
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()

        # Close database connection
        cursor.close()
        conn.close()

        return jsonify({
            'status': 'success', 
            'data': users
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

# Get User by ID Route
@user_bp.route('/<int:id>', methods=['GET'])
def get_user_by_id(id):
    try:
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Find user by ID
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (id,))
        user = cursor.fetchone()

        # Close database connection
        cursor.close()
        conn.close()

        if not user:
            return jsonify({
                'status': 'fail', 
                'message': 'User not found'
            }), 404

        return jsonify({
            'status': 'success', 
            'data': user
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

# Update User Route
@user_bp.route('/<int:id>', methods=['PUT'])
@verify_token
def update_user(id):
    data = request.get_json()

    # Fetch existing user data first to retain unchanged fields
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (id,))
        existing_user = cursor.fetchone()

        if not existing_user:
            return jsonify({'status': 'fail', 'message': 'User not found'}), 404

        # Use the existing values if new values are not provided
        username = data.get('username', existing_user['username'])
        email = data.get('email', existing_user['email'])
        password = data.get('password')
        fullname = data.get('fullname', existing_user['fullname'])
        role = data.get('role', existing_user['role'])
        posisi = data.get('posisi', existing_user['posisi'])

        # If password is provided, hash it
        if password:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        else:
            hashed_password = existing_user['password']  # Retain existing password if not updated

        # Update user in the database
        cursor.execute('''
            UPDATE users 
            SET username = %s, email = %s, password = %s, 
                fullname = %s, role = %s, posisi = %s 
            WHERE user_id = %s
        ''', (username, email, hashed_password, fullname, role, posisi, id))

        # Commit the transaction
        conn.commit()

        # Close database connection
        cursor.close()
        conn.close()

        return jsonify({
            'status': 'success', 
            'message': 'User updated successfully'
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

# Delete User Route
@user_bp.route('/<int:id>', methods=['DELETE'])
def delete_user(id):
    try:
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete user from the users table (trigger handles related deletions)
        cursor.execute('DELETE FROM users WHERE user_id = %s', (id,))

        # Commit the transaction
        conn.commit()

        # Close database connection
        cursor.close()
        conn.close()

        return jsonify({
            'status': 'success', 
            'message': 'User deleted successfully along with related data'
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500