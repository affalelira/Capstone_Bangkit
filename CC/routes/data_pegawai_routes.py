from flask import Blueprint, jsonify, request
import mysql.connector
from functools import wraps
import jwt
import logging
import os
from dotenv import load_dotenv
from routes.user_routes import verify_token

# Create a Blueprint for parameter_gaji routes
data_pegawai_bp = Blueprint('data_pegawai', __name__)

# Load environment variables
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

#Create
@data_pegawai_bp.route('/<int:user_id>', methods=['PUT'])
@verify_token
def add_pegawai(user_id):
    try:
        # Mengambil data dari body request (JSON)
        data = request.get_json()

        # Ambil data lainnya seperti NIK, TTL, alamat, dll.
        nik = data.get('NIK')
        ttl = data.get('TTL')
        alamat = data.get('alamat')
        jenis_kelamin = data.get('jenis_kelamin')
        no_wa = data.get('no_wa')
        no_rek = data.get('no_rek')
        agama = data.get('agama')

        # Koneksi ke database
        connection = get_db_connection()
        if connection is None:
            return jsonify({"status": "error", "message": "Gagal koneksi ke database"}), 500

        cursor = connection.cursor()

        # Mengecek apakah user_id ada di tabel user
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()

        if user_data is None:
            return jsonify({
                "status": "error",
                "message": f"User dengan user_id {user_id} tidak ditemukan",
                "data": None
            }), 400

        # Menggunakan UPDATE untuk memperbarui data pegawai
        update_query = """
        UPDATE data_pegawai
        SET NIK = %s, TTL = %s, alamat = %s, jenis_kelamin = %s, no_wa = %s, no_rek = %s, agama = %s
        WHERE user_id = %s
        """
        cursor.execute(update_query, (nik, ttl, alamat, jenis_kelamin, no_wa, no_rek, agama, user_id))
        connection.commit()

        # Cek apakah ada perubahan data
        if cursor.rowcount > 0:
            return jsonify({"status": "success", "message": "Data pegawai berhasil ditambahkan"}), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Tidak ada data yang ditambahkan, pastikan anda adalah karyawan aktif",
                "data": None
            }), 400

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": "Gagal memperbarui data pegawai"}), 500
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"status": "error", "message": "Terjadi kesalahan saat memproses permintaan"}), 500

#GetAll
@data_pegawai_bp.route('/', methods=['GET'])
@verify_token
def get_all_pegawai():
    try:
        # Koneksi ke database
        connection = get_db_connection()
        if connection is None:
            return jsonify({
                "status": "error",
                "message": "Gagal koneksi ke database",
                "data": None
            }), 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM data_pegawai")
        pegawai_data = cursor.fetchall()

        if pegawai_data:
            return jsonify({
                "status": "success",
                "message": "Data pegawai berhasil diambil",
                "data": pegawai_data
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Data pegawai tidak ditemukan",
                "data": None
            }), 404

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan saat mengambil data pegawai: {err}",
            "data": None
        }), 500

#GetbyID
@data_pegawai_bp.route('//<int:user_id>', methods=['GET'])
@verify_token
def get_pegawai_by_id(user_id):
    try:
        # Koneksi ke database
        connection = get_db_connection()
        if connection is None:
            return jsonify({
                "status": "error",
                "message": "Gagal koneksi ke database",
                "data": None
            }), 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM data_pegawai WHERE user_id = %s", (user_id,))
        pegawai_data = cursor.fetchone()

        if pegawai_data:
            return jsonify({
                "status": "success",
                "message": "Data pegawai berhasil diambil",
                "data": pegawai_data
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Data pegawai tidak ditemukan",
                "data": None
            }), 404

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan saat mengambil data pegawai: {err}",
            "data": None
        }), 500

#Update
@data_pegawai_bp.route('/update/<int:user_id>', methods=['PUT'])
@verify_token
def update_pegawai(user_id):
    data = request.get_json()  
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM data_pegawai WHERE user_id = %s", (user_id,))
        existing_data = cursor.fetchone()

        if not existing_data:
            return jsonify({'status': 'fail', 'message': 'Data pegawai tidak ditemukan'}), 404

        nik = data.get('NIK', existing_data["NIK"])
        ttl = data.get('TTL', existing_data["TTL"])
        alamat = data.get('alamat', existing_data["alamat"])
        jenis_kelamin = data.get('jenis_kelamin', existing_data["jenis_kelamin"])
        no_wa = data.get('no_wa', existing_data["no_wa"])
        no_rek = data.get('no_rek', existing_data["no_rek"])
        agama = data.get('agama', existing_data["agama"])

        update_query = """
        UPDATE data_pegawai
        SET NIK = %s, TTL = %s, alamat = %s, jenis_kelamin = %s, no_wa = %s, no_rek = %s, agama = %s
        WHERE user_id = %s
        """
    
        cursor.execute(update_query, (nik, ttl, alamat, jenis_kelamin, no_wa, no_rek, agama, user_id))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({"status": "success", "message": "Data pegawai berhasil diperbarui"}), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Tidak ada data yang diperbarui, pastikan data yang diupdate valid",
                "data": None
            }), 400

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": "Gagal memperbarui data pegawai"}), 500
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"status": "error", "message": "Terjadi kesalahan saat memproses permintaan"}), 500

#Delete
@data_pegawai_bp.route('/<int:user_id>', methods=['DELETE'])
def delete_pegawai(user_id):
    try:
        # Koneksi ke database
        connection = get_db_connection()
        if connection is None:
            return jsonify({"status": "error", "message": "Gagal koneksi ke database"}), 500

        cursor = connection.cursor()
        cursor.execute("DELETE FROM data_pegawai WHERE user_id = %s", (user_id,))
        connection.commit()

        return jsonify({"status": "success", "message": "Data pegawai berhasil dihapus"}), 200

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": "Gagal menghapus data pegawai"}), 500
