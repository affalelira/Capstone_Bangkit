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
gaji_karyawan_bp = Blueprint('gaji_karyawan', __name__)

# Secret key for JWT token generation
SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

#POST
@gaji_karyawan_bp.route('/', methods=['POST'])
def add_gaji():
    try:
        data = request.get_json()  # Mengambil data JSON dari request

        # Ambil data dari request body
        user_id = data.get('user_id')
        bulan = data.get('bulan')
        tahun = data.get('tahun')
        tot_hari_kerja = data.get('tot_hari_kerja')
        tot_kehadiran = data.get('tot_kehadiran')
        insentif = data.get('insentif')
        telat = data.get('telat')
        absen = data.get('absen')
        lembur = data.get('lembur')
        total_gaji = data.get('total_gaji')

        # Koneksi ke database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert data gaji
        insert_query = """
        INSERT INTO gaji_karyawan (user_id, bulan, tahun, tot_hari_kerja, tot_kehadiran, insentif, telat, absen, lembur, total_gaji)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (user_id, bulan, tahun, tot_hari_kerja, tot_kehadiran, insentif, telat, absen, lembur, total_gaji))
        conn.commit()

        return jsonify({"status": "success", "message": "Data gaji berhasil ditambahkan"}), 201

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": "Gagal menambahkan data gaji"}), 500
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"status": "error", "message": "Terjadi kesalahan saat memproses permintaan"}), 500

#GET
@gaji_karyawan_bp.route('/', methods=['GET'])
def get_all_gaji():
    try:
        # Koneksi ke database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM gaji_karyawan")
        gaji_data = cursor.fetchall()

        if gaji_data:
            return jsonify({"status": "success", "message": "Data gaji berhasil diambil", "data": gaji_data}), 200
        else:
            return jsonify({"status": "error", "message": "Data gaji tidak ditemukan", "data": None}), 404

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": f"Terjadi kesalahan saat mengambil data gaji: {err}", "data": None}), 500

@gaji_karyawan_bp.route('/<int:user_id>', methods=['GET'])
def get_gaji_by_id(user_id):
    try:
        # Koneksi ke database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM gaji_karyawan WHERE user_id = %s", (user_id,))
        gaji_data = cursor.fetchall()

        if gaji_data:
            return jsonify({"status": "success", "message": "Data gaji berhasil diambil", "data": gaji_data}), 200
        else:
            return jsonify({"status": "error", "message": "Data gaji tidak ditemukan", "data": None}), 404

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": f"Terjadi kesalahan saat mengambil data gaji: {err}", "data": None}), 500

#PUT
@gaji_karyawan_bp.route('/<int:gaji_id>', methods=['PUT'])
def update_gaji(gaji_id):
    data = request.get_json()  
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM gaji_karyawan WHERE gaji_id = %s", (gaji_id,))
        existing_data = cursor.fetchone()

        if not existing_data:
            return jsonify({'status': 'fail', 'message': 'Gaji ID not found'}), 404
        
        # Ambil data yang ingin diupdate
        bulan = data.get('bulan', existing_data['bulan'])
        tahun = data.get('tahun', existing_data['tahun'])
        tot_hari_kerja = data.get('tot_hari_kerja', existing_data['tot_hari_kerja'])
        tot_kehadiran = data.get('tot_hari_kerja', existing_data['tot_hari_kerja'])
        insentif = data.get('insentif', existing_data['insentif'])
        telat = data.get('telat', existing_data['telat'])
        absen = data.get('absen', existing_data['absen'])
        lembur = data.get('lembur', existing_data['lembur'])
        total_gaji = data.get('total_gaji', existing_data['total_gaji'])

        # Update the database with the new or retained values
        cursor.execute("""
        UPDATE gaji_karyawan
        SET bulan = %s, tahun = %s, tot_hari_kerja = %s, tot_kehadiran = %s, insentif = %s, telat = %s, absen = %s, lembur = %s, total_gaji = %s
        WHERE gaji_id = %s
        """, (bulan, tahun, tot_hari_kerja, tot_kehadiran, insentif, telat, absen, lembur, total_gaji, gaji_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Data gaji berhasil diperbarui"}), 200

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": "Gagal memperbarui data gaji"}), 500
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"status": "error", "message": "Terjadi kesalahan saat memproses permintaan"}), 500

#DELETE
@gaji_karyawan_bp.route('/<int:gaji_id>', methods=['DELETE'])
def delete_gaji(gaji_id):
    try:
        # Koneksi ke database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Menghapus data gaji berdasarkan gaji_id
        delete_query = "DELETE FROM gaji_karyawan WHERE gaji_id = %s"
        cursor.execute(delete_query, (gaji_id,))
        conn.commit()

        return jsonify({"status": "success", "message": "Data gaji berhasil dihapus"}), 200

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"status": "error", "message": "Gagal menghapus data gaji"}), 500
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"status": "error", "message": "Terjadi kesalahan saat menghapus data gaji"}), 500
