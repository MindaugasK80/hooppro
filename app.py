from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "hooppro.db"
app = Flask(__name__)
app.secret_key = "hooppro-demo-change-me"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'player'
    );
    CREATE TABLE IF NOT EXISTS trainings(
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
      date TEXT NOT NULL, time TEXT NOT NULL, location TEXT NOT NULL,
      capacity INTEGER NOT NULL DEFAULT 1, description TEXT
    );
    CREATE TABLE IF NOT EXISTS bookings(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      training_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'confirmed',
      UNIQUE(user_id,training_id),
      FOREIGN KEY(user_id) REFERENCES users(id),
      FOREIGN KEY(training_id) REFERENCES trainings(id)
    );
    """)
    if not c.execute("SELECT id FROM users WHERE email='admin@hooppro.lt'").fetchone():
        c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                  ("HoopPro Administratorius","admin@hooppro.lt",
                   generate_password_hash("Admin123!"),"admin"))
    if c.execute("SELECT COUNT(*) n FROM trainings").fetchone()["n"] == 0:
        demo = [
          ("Metimo technika","2026-09-02","17:00","Šiaulių sporto arena",4,"Metimo mechanika, kojų darbas ir metimai po driblingo."),
          ("Kamuolio valdymas","2026-09-04","18:30","Šiaulių sporto arena",3,"Driblingas, krypties keitimas ir greitis."),
          ("Individuali 1:1 treniruotė","2026-09-07","16:00","Šiaulių sporto arena",1,"Individualus darbas pagal žaidėjo poreikius.")
        ]
        c.executemany("INSERT INTO trainings(title,date,time,location,capacity,description) VALUES(?,?,?,?,?,?)",demo)
    c.commit(); c.close()

def user():
    if "uid" not in session: return None
    c=db(); u=c.execute("SELECT * FROM users WHERE id=?",(session["uid"],)).fetchone(); c.close()
    return u

def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not user():
            flash("Prisijunkite, kad galėtumėte registruotis.","warning")
            return redirect(url_for("login"))
        return fn(*a,**kw)
    return w

def admin_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not user() or user()["role"]!="admin":
            flash("Prieiga skirta administratoriui.","danger")
            return redirect(url_for("home"))
        return fn(*a,**kw)
    return w

@app.context_processor
def ctx(): return {"current_user":user()}

@app.route("/")
def home():
    c=db()
    rows=c.execute("""SELECT t.*,
      (SELECT COUNT(*) FROM bookings b WHERE b.training_id=t.id AND b.status='confirmed') booked
      FROM trainings t ORDER BY t.date,t.time""").fetchall()
    c.close()
    return render_template("home.html", trainings=rows)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form["name"].strip(); email=request.form["email"].strip().lower()
        password=request.form["password"]
        if len(password)<8:
            flash("Slaptažodis turi būti bent 8 simbolių.","danger")
            return render_template("register.html")
        c=db()
        try:
            c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                      (name,email,generate_password_hash(password)))
            c.commit()
        except sqlite3.IntegrityError:
            c.close(); flash("Šis el. paštas jau užregistruotas.","danger")
            return render_template("register.html")
        c.close(); flash("Paskyra sukurta. Prisijunkite.","success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=db(); u=c.execute("SELECT * FROM users WHERE email=?",(request.form["email"].strip().lower(),)).fetchone(); c.close()
        if u and check_password_hash(u["password"],request.form["password"]):
            session["uid"]=u["id"]
            return redirect(url_for("admin" if u["role"]=="admin" else "dashboard"))
        flash("Neteisingi prisijungimo duomenys.","danger")
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.post("/book/<int:tid>")
@login_required
def book(tid):
    c=db(); u=user()
    t=c.execute("SELECT * FROM trainings WHERE id=?",(tid,)).fetchone()
    count=c.execute("SELECT COUNT(*) n FROM bookings WHERE training_id=? AND status='confirmed'",(tid,)).fetchone()["n"]
    exists=c.execute("SELECT id FROM bookings WHERE user_id=? AND training_id=? AND status='confirmed'",
                     (u["id"],tid)).fetchone()
    if not t: flash("Treniruotė nerasta.","danger")
    elif exists: flash("Jūs jau užsiregistravote.","warning")
    elif count>=t["capacity"]: flash("Laisvų vietų nebėra.","danger")
    else:
        c.execute("INSERT INTO bookings(user_id,training_id) VALUES(?,?)",(u["id"],tid)); c.commit()
        flash("Registracija patvirtinta!","success")
    c.close(); return redirect(url_for("dashboard"))

@app.get("/dashboard")
@login_required
def dashboard():
    c=db()
    rows=c.execute("""SELECT b.*,t.title,t.date,t.time,t.location,t.description
      FROM bookings b JOIN trainings t ON t.id=b.training_id
      WHERE b.user_id=? ORDER BY t.date,t.time""",(user()["id"],)).fetchall()
    c.close(); return render_template("dashboard.html",bookings=rows)

@app.post("/cancel/<int:bid>")
@login_required
def cancel(bid):
    c=db(); c.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND user_id=?",(bid,user()["id"]))
    c.commit(); c.close(); flash("Registracija atšaukta.","success"); return redirect(url_for("dashboard"))

@app.get("/admin")
@admin_required
def admin():
    c=db()
    trainings=c.execute("""SELECT t.*,(SELECT COUNT(*) FROM bookings b WHERE b.training_id=t.id AND b.status='confirmed') booked
      FROM trainings t ORDER BY t.date,t.time""").fetchall()
    players=c.execute("SELECT * FROM users WHERE role='player' ORDER BY name").fetchall()
    c.close(); return render_template("admin.html",trainings=trainings,players=players)

@app.post("/admin/create")
@admin_required
def create():
    f=request.form; c=db()
    c.execute("INSERT INTO trainings(title,date,time,location,capacity,description) VALUES(?,?,?,?,?,?)",
              (f["title"],f["date"],f["time"],f["location"],int(f["capacity"]),f.get("description","")))
    c.commit(); c.close(); flash("Treniruotė sukurta.","success"); return redirect(url_for("admin"))

@app.post("/admin/delete/<int:tid>")
@admin_required
def delete(tid):
    c=db(); c.execute("DELETE FROM bookings WHERE training_id=?",(tid,)); c.execute("DELETE FROM trainings WHERE id=?",(tid,))
    c.commit(); c.close(); flash("Treniruotė ištrinta.","success"); return redirect(url_for("admin"))

if __name__=="__main__":
    init_db()
    app.run(debug=True,host="127.0.0.1",port=5000)
