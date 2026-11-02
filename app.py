"""Modul backend autentikasi Flask dengan antarmuka web interaktif."""

import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/users.db")


def init_db():
    """Inisialisasi database dan memastikan username tetap unik."""
    database = Path(DATABASE_PATH)
    database.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DATABASE_PATH, timeout=30)

    try:
        # Mengunci transaksi agar inisialisasi antar-worker teratur.
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT,
                password TEXT
            )
            """
        )

        # Pastikan akun admin yang duplikat memiliki password sama.
        admin_state = cursor.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT password)
            FROM users
            WHERE username = ?
            """,
            ("admin",),
        ).fetchone()

        if admin_state[1] > 1:
            raise RuntimeError(
                "Akun admin memiliki password berbeda. "
                "Inisialisasi dibatalkan."
            )

        # Pertahankan satu baris admin dan hapus duplikatnya.
        cursor.execute(
            """
            DELETE FROM users
            WHERE username = ?
            AND rowid NOT IN (
                SELECT MIN(rowid)
                FROM users
                WHERE username = ?
            )
            """,
            ("admin", "admin"),
        )

        # Terapkan keunikan username pada seluruh tabel.
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
            ON users(username)
            """
        )

        # Buat akun admin hanya jika belum tersedia.
        cursor.execute(
            """
            INSERT INTO users (username, password)
            SELECT ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM users WHERE username = ?
            )
            """,
            ("admin", "supersecret", "admin"),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.route("/health", methods=["GET"])
def health():
    """Memeriksa kesiapan aplikasi dan koneksi database."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return jsonify({"status": "healthy"}), 200
    except sqlite3.Error:
        return jsonify({"status": "unhealthy"}), 503


@app.route("/", methods=["GET", "POST"])
def index():
    """Menampilkan formulir login dan memproses autentikasi."""
    message = None
    status_class = None

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        conn = sqlite3.connect(DATABASE_PATH)
        try:
            cursor = conn.cursor()
            query = (
                "SELECT * FROM users "
                "WHERE username = ? AND password = ?"
            )
            cursor.execute(query, (username, password))
            user = cursor.fetchone()
        finally:
            conn.close()

        if user:
            message = "Login Berhasil! Selamat datang."
            status_class = "success"
        else:
            message = "Login Gagal! Kredensial tidak valid."
            status_class = "danger"

    return render_template(
        "index.html", message=message, status_class=status_class
    )


@app.route("/dashboard")
def dashboard():
    """Route tambahan untuk pengujian CI/CD."""
    return "Selamat Datang di Dashboard Baru!"


# Inisialisasi database saat aplikasi dimuat oleh Gunicorn.
init_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
