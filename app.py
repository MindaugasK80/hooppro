from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hooppro-demo-change-me")


def db():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL aplinkos kintamasis nerastas.")

    return psycopg2.connect(database_url)


def init_db():
    c = db()
    cur = c.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'player'
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings(
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 1,
            description TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            training_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            UNIQUE(user_id, training_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(training_id) REFERENCES trainings(id)
        );
    """)

    cur.execute(
        "SELECT id FROM users WHERE email = %s",
        ("admin@hooppro.lt",)
    )

    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO users(name, email, password, role)
            VALUES(%s, %s, %s, %s)
            """,
            (
                "HoopPro Administratorius",
                "admin@hooppro.lt",
                generate_password_hash("Admin123!"),
                "admin"
            )
        )

    cur.execute("SELECT COUNT(*) AS n FROM trainings")
    count = cur.fetchone()[0]

    if count == 0:
        demo = [
            (
                "Metimo technika",
                "2026-09-02",
                "17:00",
                "Šiaulių sporto arena",
                4,
                "Metimo mechanika, kojų darbas ir metimai po driblingo."
            ),
            (
                "Kamuolio valdymas",
                "2026-09-04",
                "18:30",
                "Šiaulių sporto arena",
                3,
                "Driblingas, krypties keitimas ir greitis."
            ),
            (
                "Individuali 1:1 treniruotė",
                "2026-09-07",
                "16:00",
                "Šiaulių sporto arena",
                1,
                "Individualus darbas pagal žaidėjo poreikius."
            )
        ]

        cur.executemany(
            """
            INSERT INTO trainings(
                title, date, time, location, capacity, description
            )
            VALUES(%s, %s, %s, %s, %s, %s)
            """,
            demo
        )

    c.commit()
    cur.close()
    c.close()


def user():
    if "uid" not in session:
        return None

    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT * FROM users WHERE id = %s",
        (session["uid"],)
    )

    u = cur.fetchone()

    cur.close()
    c.close()

    return u


def login_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if not user():
            flash(
                "Prisijunkite, kad galėtumėte registruotis.",
                "warning"
            )
            return redirect(url_for("login"))

        return fn(*a, **kw)

    return w


def admin_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        current_user = user()

        if not current_user or current_user["role"] != "admin":
            flash(
                "Prieiga skirta administratoriui.",
                "danger"
            )
            return redirect(url_for("home"))

        return fn(*a, **kw)

    return w


@app.context_processor
def ctx():
    return {"current_user": user()}


@app.route("/")
def home():
    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            t.*,
            (
                SELECT COUNT(*)
                FROM bookings b
                WHERE b.training_id = t.id
                AND b.status = 'confirmed'
            ) AS booked
        FROM trainings t
        ORDER BY t.date, t.time
    """)

    rows = cur.fetchall()

    cur.close()
    c.close()

    return render_template("home.html", trainings=rows)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if len(password) < 8:
            flash(
                "Slaptažodis turi būti bent 8 simbolių.",
                "danger"
            )
            return render_template("register.html")

        c = db()
        cur = c.cursor()

        try:
            cur.execute(
                """
                INSERT INTO users(name, email, password)
                VALUES(%s, %s, %s)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password)
                )
            )

            c.commit()

        except psycopg2.errors.UniqueViolation:
            c.rollback()
            cur.close()
            c.close()

            flash(
                "Šis el. paštas jau užregistruotas.",
                "danger"
            )

            return render_template("register.html")

        cur.close()
        c.close()

        flash(
            "Paskyra sukurta. Prisijunkite.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        c = db()
        cur = c.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT * FROM users WHERE email = %s",
            (
                request.form["email"].strip().lower(),
            )
        )

        u = cur.fetchone()

        cur.close()
        c.close()

        if u and check_password_hash(
            u["password"],
            request.form["password"]
        ):
            session["uid"] = u["id"]

            if u["role"] == "admin":
                return redirect(url_for("admin"))

            return redirect(url_for("dashboard"))

        flash(
            "Neteisingi prisijungimo duomenys.",
            "danger"
        )

    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.post("/book/<int:tid>")
@login_required
def book(tid):
    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    current_user = user()

    cur.execute(
        "SELECT * FROM trainings WHERE id = %s",
        (tid,)
    )

    t = cur.fetchone()

    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM bookings
        WHERE training_id = %s
        AND status = 'confirmed'
        """,
        (tid,)
    )

    count = cur.fetchone()["n"]

    cur.execute(
        """
        SELECT id
        FROM bookings
        WHERE user_id = %s
        AND training_id = %s
        AND status = 'confirmed'
        """,
        (
            current_user["id"],
            tid
        )
    )

    exists = cur.fetchone()

    if not t:
        flash(
            "Treniruotė nerasta.",
            "danger"
        )

    elif exists:
        flash(
            "Jūs jau užsiregistravote.",
            "warning"
        )

    elif count >= t["capacity"]:
        flash(
            "Laisvų vietų nebėra.",
            "danger"
        )

    else:
        try:
            cur.execute(
                """
                INSERT INTO bookings(user_id, training_id)
                VALUES(%s, %s)
                """,
                (
                    current_user["id"],
                    tid
                )
            )

            c.commit()

            flash(
                "Registracija patvirtinta!",
                "success"
            )

        except psycopg2.IntegrityError:
            c.rollback()

            flash(
                "Nepavyko užregistruoti į treniruotę.",
                "danger"
            )

    cur.close()
    c.close()

    return redirect(url_for("dashboard"))


@app.get("/dashboard")
@login_required
def dashboard():
    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    current_user = user()

    cur.execute(
        """
        SELECT
            b.*,
            t.title,
            t.date,
            t.time,
            t.location,
            t.description
        FROM bookings b
        JOIN trainings t
            ON t.id = b.training_id
        WHERE b.user_id = %s
        ORDER BY t.date, t.time
        """,
        (
            current_user["id"],
        )
    )

    rows = cur.fetchall()

    cur.close()
    c.close()

    return render_template(
        "dashboard.html",
        bookings=rows
    )


@app.post("/cancel/<int:bid>")
@login_required
def cancel(bid):
    c = db()
    cur = c.cursor()

    current_user = user()

    cur.execute(
        """
        UPDATE bookings
        SET status = 'cancelled'
        WHERE id = %s
        AND user_id = %s
        """,
        (
            bid,
            current_user["id"]
        )
    )

    c.commit()

    cur.close()
    c.close()

    flash(
        "Registracija atšaukta.",
        "success"
    )

    return redirect(url_for("dashboard"))


@app.get("/admin")
@admin_required
def admin():
    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT
            t.*,
            (
                SELECT COUNT(*)
                FROM bookings b
                WHERE b.training_id = t.id
                AND b.status = 'confirmed'
            ) AS booked
        FROM trainings t
        ORDER BY t.date, t.time
        """
    )

    trainings = cur.fetchall()

    cur.execute(
        """
        SELECT *
        FROM users
        WHERE role = 'player'
        ORDER BY name
        """
    )

    players = cur.fetchall()

    cur.close()
    c.close()

    return render_template(
        "admin.html",
        trainings=trainings,
        players=players
    )


@app.post("/admin/create")
@admin_required
def create():
    f = request.form

    c = db()
    cur = c.cursor()

    cur.execute(
        """
        INSERT INTO trainings(
            title,
            date,
            time,
            location,
            capacity,
            description
        )
        VALUES(%s, %s, %s, %s, %s, %s)
        """,
        (
            f["title"],
            f["date"],
            f["time"],
            f["location"],
            int(f["capacity"]),
            f.get("description", "")
        )
    )

    c.commit()

    cur.close()
    c.close()

    flash(
        "Treniruotė sukurta.",
        "success"
    )

    return redirect(url_for("admin"))


@app.post("/admin/delete/<int:tid>")
@admin_required
def delete(tid):
    c = db()
    cur = c.cursor()

    cur.execute(
        "DELETE FROM bookings WHERE training_id = %s",
        (tid,)
    )

    cur.execute(
        "DELETE FROM trainings WHERE id = %s",
        (tid,)
    )

    c.commit()

    cur.close()
    c.close()

    flash(
        "Treniruotė ištrinta.",
        "success"
    )

    return redirect(url_for("admin"))


# Sukuriame PostgreSQL lenteles paleidžiant programą.
init_db()


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
