from flask import Blueprint, jsonify, request
import mysql.connector
from functools import wraps
import jwt
import logging
import os
from dotenv import load_dotenv
from routes.user_routes import verify_token

# Muat file .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Create a Blueprint for parameter_gaji routes
parameter_gaji_bp = Blueprint('parameter_gaji', __name__)

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 1. Create (C) - Insert new data
@parameter_gaji_bp.route('/', methods=['POST'])
@verify_token
def create_parameter_gaji():
    data = request.get_json()
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'fail', 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO parameter_gaji (posisi, insentif, telat, absen, lembur) VALUES (%s, %s, %s, %s, %s)",
            (data['posisi'], data['insentif'], data['telat'], data['absen'], data['lembur'])
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Parameter Gaji added successfully'}), 201
    except Exception as e:
        logger.error(f"Error creating parameter_gaji: {e}")
        return jsonify({'status': 'fail', 'message': 'Failed to add parameter_gaji'}), 500

# 2. Read (R) 
@parameter_gaji_bp.route('/', methods=['GET'])
@verify_token
def read_parameter_gaji():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM parameter_gaji")
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if results:
            return jsonify({'status': 'success', 'data': results}), 200
        else:
            return jsonify({'status': 'fail', 'message': 'Parameter Gaji not found'}), 404
    except Exception as e:
        logger.error(f"Error reading parameter_gaji: {e}")
        return jsonify({'status': 'fail', 'message': 'Failed to fetch parameter_gaji'}), 500


@parameter_gaji_bp.route('/<int:parameter_id>', methods=['GET'])
@verify_token
def read_parameter_gaji_id(parameter_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM parameter_gaji WHERE parameter_id = %s", (parameter_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify({'status': 'success', 'data': result}), 200
        else:
            return jsonify({'status': 'fail', 'message': 'Parameter Gaji not found'}), 404
    except Exception as e:
        logger.error(f"Error reading parameter_gaji: {e}")
        return jsonify({'status': 'fail', 'message': 'Failed to fetch parameter_gaji'}), 500

# 3. Update (U) - Update data by parameter_id
@parameter_gaji_bp.route('/<int:parameter_id>', methods=['PUT'])
@verify_token
def update_parameter_gaji(parameter_id):
    data = request.get_json()

    # Fetch existing parameter data first to retain unchanged fields
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM parameter_gaji WHERE parameter_id = %s", (parameter_id,))
        existing_data = cursor.fetchone()

        if not existing_data:
            return jsonify({'status': 'fail', 'message': 'Parameter Gaji not found'}), 404
        
        # Use existing values if new values are not provided
        posisi = data.get("posisi", existing_data["posisi"])
        insentif = data.get("insentif", existing_data["insentif"])
        telat = data.get("telat", existing_data["telat"])
        absen = data.get("absen", existing_data["absen"])
        lembur = data.get("lembur", existing_data["lembur"])

        # Update the database with the new or retained values
        cursor.execute("""
            UPDATE parameter_gaji
            SET posisi = %s, insentif = %s, telat = %s, absen = %s, lembur = %s
            WHERE parameter_id = %s
        """, (posisi, insentif, telat, absen, lembur, parameter_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Parameter Gaji updated successfully'}), 200
    except Exception as e:
        logger.error(f"Error updating parameter_gaji: {e}")
        return jsonify({'status': 'fail', 'message': 'Failed to update parameter_gaji'}), 500

# 4. Delete (D) - Delete data by parameter_id
@parameter_gaji_bp.route('/<int:parameter_id>', methods=['DELETE'])
@verify_token
def delete_parameter_gaji(parameter_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'fail', 'message': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM parameter_gaji WHERE parameter_id = %s", (parameter_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Parameter Gaji deleted successfully'}), 200
    except Exception as e:
        logger.error(f"Error deleting parameter_gaji: {e}")
        return jsonify({'status': 'fail', 'message': 'Failed to delete parameter_gaji'}), 500
