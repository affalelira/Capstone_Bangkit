import os
from flask import Flask
from flask_cors import CORS
from routes.user_routes import user_bp
from routes.log_kehadiran_routes import face_recognition_bp
from routes.parameter_gaji_routes import parameter_gaji_bp
from routes.data_pegawai_routes import data_pegawai_bp
from routes.gaji_karyawan_routes import gaji_karyawan_bp
from dotenv import load_dotenv


# Muat file .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def create_app():
    # Inisialisasi Flask app
    app = Flask(__name__)
    
    # Aktifkan CORS untuk semua route
    CORS(app)
    
    # Konfigurasi secret key dari environment variable
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
    
    # Konfigurasi database
    app.config['DB_HOST'] = os.getenv('DB_HOST')
    app.config['DB_USER'] = os.getenv('DB_USER')
    app.config['DB_PASSWORD'] = os.getenv('DB_PASSWORD')
    app.config['DB_NAME'] = os.getenv('DB_NAME')
    
    # Register blueprint
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(face_recognition_bp, url_prefix='/api/log_kehadiran')
    app.register_blueprint(data_pegawai_bp, url_prefix='/api/data_pegawai')
    app.register_blueprint(parameter_gaji_bp, url_prefix='/api/parameter_gaji')
    app.register_blueprint(gaji_karyawan_bp, url_prefix='/api/gaji')
    
    return app

# Jalankan aplikasi
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8080)