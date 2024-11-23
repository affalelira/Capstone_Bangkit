from flask import Flask, request, jsonify
import numpy as np
from datetime import datetime
from google.cloud import storage
from tensorflow.keras.models import load_model
from PIL import Image
import pymysql
import logging
import os

# Inisialisasi Flask app
app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.INFO)

# Konfigurasi database Cloud SQL
DB_CONFIG = {
    'host': '127.0.0.1',  # Cloud SQL Proxy akan berjalan di localhost
    'user': 'ajeng',  # Ganti dengan username database
    'password': 'ajengcans',  # Ganti dengan password database
    'database': 'aji-capstone'  # Ganti dengan nama database Anda
}

# Inisialisasi Google Cloud Storage menggunakan service account
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "flash-gasket-442211-a6-3f6524131d4c.json"  
storage_client = storage.Client()
bucket_name = 'aji-capstone-bucket'
bucket = storage_client.bucket(bucket_name)

# Load model machine learning
MODEL_PATH = 'https://storage.googleapis.com/aji-capstone-bucket/user_and_model/siamese_model.h5'
model = load_model(MODEL_PATH)

# Fungsi untuk mengunduh gambar dari Google Cloud Storage
def download_user_image_from_gcs(id_karyawan):
    try:
        # Path file sesuai folder di bucket
        image_file_name = f"user{id_karyawan}.jpg"
        blob = bucket.blob(f"user_and_model/{image_file_name}")
        
        if not blob.exists():
            raise FileNotFoundError(f"Image for employee {id_karyawan} not found in GCS.")
        
        img_path = f"/tmp/{image_file_name}"  # Tempat penyimpanan sementara
        blob.download_to_filename(img_path)
        return img_path
    except Exception as e:
        logging.error(f"Error accessing Google Cloud Storage: {e}")
        raise

# Fungsi untuk memproses gambar
def preprocess_image(img_path, target_size=(120, 120)):
    try:
        img = Image.open(img_path).convert('L').resize(target_size)  # Grayscale dan resize
        img_array = np.array(img) / 255.0  # Normalisasi ke [0, 1]
        img_array = np.expand_dims(img_array, axis=-1)  # Tambahkan channel dimension
        img_array = np.expand_dims(img_array, axis=0)  # Tambahkan batch dimension
        return img_array
    except Exception as e:
        logging.error(f"Error preprocessing image: {e}")
        raise

# Fungsi untuk prediksi kesamaan gambar
def predict_similarity(image1, image2):
    try:
        image1 = preprocess_image(image1)
        image2 = preprocess_image(image2)
        similarity_score = model.predict([image1, image2])
        return similarity_score[0][0]
    except Exception as e:
        logging.error(f"Error predicting similarity: {e}")
        raise

# Fungsi untuk menyisipkan log ke database
def insert_log(id_karyawan, status):
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO log_kehadiran (id_karyawan, login_time, tanggal, status)
                VALUES (%s, %s, %s, %s)
            """
            now = datetime.now()
            data = (id_karyawan, now, now.date(), status)
            cursor.execute(sql, data)
        connection.commit()
    except pymysql.MySQLError as e:
        logging.error(f"Database error: {e}")
        raise
    finally:
        if connection:
            connection.close()

# Endpoint untuk absensi
@app.route("/absen", methods=["POST"])
def absen():
    try:
        logging.info("Processing attendance request...")

        # Validasi input
        id_karyawan = request.form.get("id_karyawan")
        file = request.files.get("foto")

        if not id_karyawan or not file:
            return jsonify({
                "status": "error",
                "message": "ID karyawan atau file gambar tidak ditemukan",
                "data": None
            }), 400

        # Validasi ukuran file
        if len(file.read()) > 10 * 1024 * 1024:  # 10 MB
            return jsonify({
                "status": "error",
                "message": "Ukuran file terlalu besar, maksimum 10 MB",
                "data": None
            }), 413

        # Validasi format file
        if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return jsonify({
                "status": "error",
                "message": "Format file tidak didukung",
                "data": None
            }), 415

        # Simpan file sementara
        img_path = f"/tmp/{id_karyawan}_scanned.jpg"
        file.seek(0)  # Reset file pointer setelah `read` sebelumnya
        file.save(img_path)

        # Unduh gambar dari GCS
        user_image_path = download_user_image_from_gcs(id_karyawan)

        # Prediksi kesamaan
        similarity_score = predict_similarity(img_path, user_image_path)
        threshold = 0.5

        if similarity_score < threshold:
            status = "valid"
            insert_log(id_karyawan, status)
            return jsonify({
                "status": "success",
                "message": "Absensi berhasil dilakukan",
                "data": {
                    "id_karyawan": id_karyawan,
                    "foto": "Foto diterima"
                }
            }), 201
        else:
            status = "invalid"
            insert_log(id_karyawan, status)
            return jsonify({
                "status": "error",
                "message": "Foto tidak dikenali dalam model",
                "data": None
            }), 400

    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return jsonify({"status": "error", "message": str(e), "data": None}), 500

# Main
if __name__ == "__main__":
    # Jalankan dengan Cloud SQL Proxy aktif
    app.run(host="0.0.0.0", port=8080, debug=True)
