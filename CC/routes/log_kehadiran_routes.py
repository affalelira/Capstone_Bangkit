import os
import logging
import numpy as np
from flask import Blueprint, request, jsonify
from PIL import Image
from google.cloud import storage
from tensorflow.keras.models import load_model
from tensorflow.keras import backend as K
from tensorflow.keras.saving import register_keras_serializable
import io
import mysql.connector
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from routes.user_routes import verify_token

# Create a Blueprint for face recognition routes
face_recognition_bp = Blueprint('face_recognition', __name__)

# Muat file .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Set kredensial Google Cloud Storage
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "routes/flash-gasket-442211-a6-3f6524131d4c.json"

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

# Konfigurasi Google Cloud Storage
BUCKET_NAME = os.getenv('BUCKET_NAME')

# Definisi fungsi jarak Euclidean untuk model Siamese
@register_keras_serializable()
def euclidean_distance(vects):
    x, y = vects
    sum_square = K.sum(K.square(x - y), axis=1, keepdims=True)
    return K.sqrt(K.maximum(sum_square, K.epsilon()))

@register_keras_serializable()
def eucl_dist_output_shape(shapes):
    shape1, shape2 = shapes
    return (shape1[0], 1)

@register_keras_serializable()
def contrastive_loss_with_margin(margin):
    def contrastive_loss(y_true, y_pred):
        square_pred = K.square(y_pred)
        margin_square = K.square(K.maximum(margin - y_pred, 0))
        return (y_true * square_pred + (1 - y_true) * margin_square)
    return contrastive_loss


# Muat model Siamese Neural Network
model = load_model(os.path.join(".", "new_siamese_model.h5"), 
    custom_objects={
        "eucl_dist_output_shape": eucl_dist_output_shape,
        "euclidean_distance": euclidean_distance,
        "contrastive_loss": contrastive_loss_with_margin(1.0)
    },
    compile=False
)

def save_attendance_log(user_id, status_login):
    connection = get_db_connection()
    if connection is None:
        return False, "Gagal koneksi ke database"
    
    try:
        cursor = connection.cursor()
        
        # Get current time in Asia/Jakarta timezone
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(jakarta_tz)
        
        # Format untuk database
        login_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
        tanggal = current_time.strftime('%Y-%m-%d')
        
        # Query untuk insert data
        insert_query = """
        INSERT INTO log_kehadiran 
        (user_id, login_time, tanggal, status_login) 
        VALUES (%s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (user_id, login_time, tanggal, status_login))  # Include status_login
        connection.commit()
        
        return True, "Log kehadiran berhasil disimpan"
        
    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return False, f"Gagal menyimpan log kehadiran: {str(err)}"
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Fungsi untuk mengunduh file dari Google Cloud Storage
def download_file_from_gcs(bucket_name, file_path):
    try:
        client = storage.Client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(file_path)
        file_content = blob.download_as_bytes()
        return file_content
    except Exception as e:
        logging.error(f"Error saat mengunduh file dari GCS: {e}")
        return None

# Fungsi untuk preprocessing gambar
def preprocess_image(image_bytes, target_size=(120, 120)):
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('L')  
        image = image.resize(target_size)
        image_array = np.array(image) / 255.0
        image_array = np.expand_dims(image_array, axis=-1)  
        return image_array
    except Exception as e:
        logging.error(f"Error saat memproses gambar: {e}")
        return None

# Fungsi untuk menghitung status login berdasarkan waktu
def calculate_login_status(login_time_str):
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    login_time = datetime.strptime(login_time_str, '%Y-%m-%d %H:%M:%S')
    login_time = login_time.replace(tzinfo=jakarta_tz)

    cutoff_time = login_time.replace(hour=9, minute=0, second=0, microsecond=0)
    cutoff_time_late = cutoff_time + timedelta(hours=1)  # jam 9 hingga 10 pagi

    time_diff = login_time - cutoff_time
    hours_late = time_diff.total_seconds() / 3600  # Mengkonversi ke jam

    if login_time < cutoff_time:
        return "on time", 0  
    elif cutoff_time <= login_time < cutoff_time_late:
        return "late", hours_late  
    else:
        return "absent", hours_late 

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

@face_recognition_bp.route('/', methods=['GET'])
@verify_token
def test_connection():
    return "Connection successful!", 200

# Route Face Recognition
@face_recognition_bp.route('/absen', methods=['POST'])
@verify_token
def absen():
    try:
        # Log start of request
        logger.info("=============== MULAI PROSES ABSENSI ===============")
        
        # Ambil data dari request
        user_id = request.form.get('user_id')
        logger.info(f"Request absensi untuk user_id: {user_id}")
        
        if 'foto' not in request.files:
            logger.error("Foto tidak ditemukan dalam request")
            return jsonify({
                "status": "error",
                "message": "Foto tidak ditemukan dalam request",
                "data": None
            }), 400

        foto = request.files['foto']
        logger.info(f"Foto diterima: {foto.filename}")

        # Validasi user_id
        if not user_id:
            logger.error("User ID tidak ditemukan")
            return jsonify({
                "status": "error",
                "message": "User ID tidak ditemukan",
                "data": None
            }), 400

        # Ambil file dari GCS
        logger.info(f"Mengambil foto referensi dari GCS untuk user_id: {user_id}")
        gcs_path = f"user_and_model/{user_id}.jpg"
        stored_image_bytes = download_file_from_gcs(BUCKET_NAME, gcs_path)
        if not stored_image_bytes:
            logger.error(f"File untuk user ID {user_id} tidak ditemukan di GCS")
            return jsonify({
                "status": "error",
                "message": f"File untuk user ID {user_id} tidak ditemukan di GCS",
                "data": None
            }), 400
        logger.info("Foto referensi berhasil diambil dari GCS")

        # Preprocess kedua gambar
        logger.info("Memulai preprocessing gambar...")
        stored_image = preprocess_image(stored_image_bytes)
        uploaded_image = preprocess_image(foto.read())

        if stored_image is None or uploaded_image is None:
            logger.error("Gambar gagal diproses pada tahap preprocessing")
            return jsonify({
                "status": "error",
                "message": "Gambar gagal diproses",
                "data": None
            }), 400
        logger.info("Preprocessing gambar selesai")

        # Persiapkan input untuk model Siamese
        logger.info("Mempersiapkan input untuk model Siamese...")
        stored_image_batch = np.expand_dims(stored_image, axis=0)
        uploaded_image_batch = np.expand_dims(uploaded_image, axis=0)

        # Buat input sesuai dengan nama layer
        inputs = {}
        input_names = [input.name.split(':')[0] for input in model.inputs]
        logger.info(f"Nama input layer model: {input_names}")
        
        if len(input_names) == 2:
            inputs[input_names[0]] = stored_image_batch
            inputs[input_names[1]] = uploaded_image_batch
            logger.info("Melakukan prediksi dengan model...")
            prediction = model.predict(inputs)[0][0]
        else:
            logger.info("Melakukan prediksi dengan input array...")
            prediction = model.predict([stored_image_batch, uploaded_image_batch])[0][0]

        similarity_threshold = 0.5
        similarity_percentage = (1 - prediction) * 100 if prediction <= 1 else 0

        # Log hasil prediksi
        logger.info(f"""
        Hasil Prediksi:
        - Prediction value: {prediction}
        - Similarity threshold: {similarity_threshold}
        - Similarity percentage: {similarity_percentage:.2f}%
        - Result: {'Match' if prediction < similarity_threshold else 'No Match'}
        """)

        if prediction < similarity_threshold:
            logger.info("Wajah terdeteksi, menyimpan ke database...")
            # Simpan log kehadiran ke database
            status_login, hours_late = calculate_login_status(datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S'))

            # Simpan log kehadiran ke database
            success, message = save_attendance_log(user_id, status_login)
            
            if not success:
                logger.error(f"Gagal menyimpan ke database: {message}")
                return jsonify({
                    "status": "error",
                    "message": f"Absensi gagal: {message}",
                    "data": None
                }), 500
            
            logger.info("Absensi berhasil disimpan ke database")
            response_data = {
                "status": "success",
                "message": "Absensi berhasil dilakukan",
                "data": {
                    "user_id": user_id,
                    "foto": foto.filename,
                    "similarity_score": float(prediction),
                    "similarity_percentage": float(similarity_percentage),
                    "threshold": float(similarity_threshold),
                    "input_names": input_names
                }
            }
            logger.info("Proses absensi selesai dengan sukses")
            logger.info("=============== AKHIR PROSES ABSENSI ===============")
            return jsonify(response_data), 201
        else:
            logger.warning(f"Wajah tidak terdeteksi untuk user_id: {user_id}")
            response_data = {
                "status": "error",
                "message": "Wajah tidak terdeteksi - Foto tidak dikenali dalam model",
                "data": {
                    "similarity_score": float(prediction),
                    "similarity_percentage": float(similarity_percentage),
                    "threshold": float(similarity_threshold),
                    "input_names": input_names
                }
            }
            logger.info("=============== AKHIR PROSES ABSENSI ===============")
            return jsonify(response_data), 400

    except Exception as e:
        logger.error(f"Error saat memproses request: {str(e)}", exc_info=True)
        logger.info("=============== AKHIR PROSES ABSENSI (ERROR) ===============")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan saat memproses absensi: {str(e)}",
            "data": None
        }), 500

@face_recognition_bp.route('/absen', methods=['GET'])
def get_all_absensi():
    try:
        connection = get_db_connection()
        if connection is None:
            return jsonify({
                "status": "error",
                "message": "Gagal koneksi ke database",
                "data": None
            }), 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM log_kehadiran")
        absensi_data = cursor.fetchall()

        return jsonify({
            "status": "success",
            "message": "Data absensi berhasil diambil",
            "data": absensi_data
        }), 200

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan saat mengambil data absensi: {err}",
            "data": None
        }), 500

@face_recognition_bp.route('/absen/<int:user_id>', methods=['GET'])
def get_absensi_by_id(user_id):
    try:
        connection = get_db_connection()
        if connection is None:
            return jsonify({
                "status": "error",
                "message": "Gagal koneksi ke database",
                "data": None
            }), 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM log_kehadiran WHERE user_id = %s", (user_id,))
        absensi_data = cursor.fetchall()

        if absensi_data:
            return jsonify({
                "status": "success",
                "message": "Data absensi berhasil diambil",
                "data": absensi_data
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Absensi tidak ditemukan",
                "data": None
            }), 404

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan saat mengambil data absensi: {err}",
            "data": None
        }), 500

@face_recognition_bp.route('/<int:log_id>', methods=['PUT'])
def update_logout_status(log_id):
    try:
        # Ambil waktu logout dari request
        logout_time = request.json.get('logout_time')
        
        if not logout_time:
            return jsonify({
                "status": "error",
                "message": "Waktu logout tidak diberikan",
                "data": None
            }), 400

        # Hitung status logout
        status_logout, overtime_hours = calculate_logout_status(logout_time)

        # Update status logout di database
        connection = get_db_connection()
        if connection is None:
            return jsonify({
                "status": "error",
                "message": "Gagal koneksi ke database",
                "data": None
            }), 500

        cursor = connection.cursor()
        update_query = """
        UPDATE log_kehadiran
        SET status_logout = %s, logout_time = %s
        WHERE log_id = %s
        """
        cursor.execute(update_query, (status_logout, logout_time, log_id))
        connection.commit()

        return jsonify({
            "status": "success",
            "message": "Status logout berhasil diperbarui",
            "data": {
                "status_logout": status_logout
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan: {str(e)}",
            "data": None
        }), 500

@face_recognition_bp.route('/<int:log_id>', methods=['DELETE'])
def delete_absensi(log_id):
    try:
        connection = get_db_connection()
        if connection is None:
            return jsonify({
                "status": "error",
                "message": "Gagal koneksi ke database",
                "data": None
            }), 500

        cursor = connection.cursor()
        cursor.execute("DELETE FROM log_kehadiran WHERE log_id = %s", (log_id,))
        connection.commit()

        return jsonify({
            "status": "success",
            "message": "Absensi berhasil dihapus",
            "data": None
        }), 200

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan saat menghapus absensi: {err}",
            "data": None
        }), 500

























