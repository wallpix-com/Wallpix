from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import sqlite3, os, uuid

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","replace-this-secret")
BASE=Path(__file__).parent
DB=BASE/"wallpix.db"
UPLOAD=BASE/"static/uploads"; UPLOAD.mkdir(parents=True,exist_ok=True)
OWNER_EMAIL=os.environ.get("OWNER_EMAIL","owner@example.com")
OWNER_PASSWORD=os.environ.get("OWNER_PASSWORD","change-me")

def con():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    c=con()
    c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT DEFAULT 'creator');
    CREATE TABLE IF NOT EXISTS photos(id INTEGER PRIMARY KEY,title TEXT,category TEXT,price REAL DEFAULT 0,creator TEXT,image TEXT,approved INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
    if c.execute("select count(*) from photos").fetchone()[0]==0:
        demo=[
        ("Aurora Mountain","Nature",0,"WallPix","https://images.unsplash.com/photo-1500534623283-312aade485b7?w=1400"),
        ("Neon City","City",1.49,"WallPix","https://images.unsplash.com/photo-1519608487953-e999c86e7455?w=1400"),
        ("Deep Space","Space",0.99,"WallPix","https://images.unsplash.com/photo-1462331940025-496dfbfc7564?w=1400"),
        ("Ocean Calm","Minimal",0.79,"WallPix","https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1400")]
        c.executemany("insert into photos(title,category,price,creator,image) values(?,?,?,?,?)",demo)
    c.commit(); c.close()
def owner(): return session.get("owner",False)

@app.context_processor
def ctx(): return {"owner":owner(),"user":session.get("user")}

@app.route("/")
def home():
    q=request.args.get("q","").strip(); cat=request.args.get("category","").strip()
    c=con(); sql="select * from photos where approved=1"; args=[]
    if q: sql+=" and (title like ? or category like ?)"; args += [f"%{q}%",f"%{q}%"]
    if cat: sql+=" and category=?"; args.append(cat)
    photos=c.execute(sql+" order by id desc",args).fetchall()
    cats=c.execute("select distinct category from photos order by category").fetchall(); c.close()
    return render_template("home.html",photos=photos,cats=cats,q=q,cat=cat)

@app.route("/photo/<int:id>")
def detail(id):
    c=con(); p=c.execute("select * from photos where id=?",(id,)).fetchone(); c.close()
    if not p: abort(404)
    return render_template("detail.html",p=p)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form["name"].strip(); email=request.form["email"].lower().strip(); pw=request.form["password"]
        c=con()
        try:
            c.execute("insert into users(name,email,password) values(?,?,?)",(name,email,generate_password_hash(pw))); c.commit()
            flash("Account created."); return redirect(url_for("login"))
        except sqlite3.IntegrityError: flash("Email already registered.")
        finally: c.close()
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"].lower().strip(); pw=request.form["password"]
        if email==OWNER_EMAIL and pw==OWNER_PASSWORD: session.clear(); session["owner"]=True; return redirect(url_for("admin"))
        c=con(); u=c.execute("select * from users where email=?",(email,)).fetchone(); c.close()
        if u and check_password_hash(u["password"],pw): session.clear(); session["user"]=u["email"]; return redirect(url_for("home"))
        flash("Invalid email or password.")
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))

@app.route("/admin",methods=["GET","POST"])
def admin():
    if not owner(): return redirect(url_for("login"))
    c=con()
    if request.method=="POST":
        c.execute("insert into photos(title,category,price,creator,image) values(?,?,?,?,?)",(request.form["title"],request.form["category"],float(request.form.get("price",0)),request.form["creator"],request.form["image"]))
        c.commit(); flash("Photo published.")
    photos=c.execute("select * from photos order by id desc").fetchall()
    users=c.execute("select count(*) n from users").fetchone()["n"]; c.close()
    return render_template("admin.html",photos=photos,users=users)

@app.post("/admin/delete/<int:id>")
def delete(id):
    if not owner(): return redirect(url_for("login"))
    c=con(); c.execute("delete from photos where id=?",(id,)); c.commit(); c.close(); flash("Photo deleted.")
    return redirect(url_for("admin"))

@app.post("/creator/upload")
def creator_upload():
    if not session.get("user") and not owner(): return redirect(url_for("login"))
    creator=session.get("user","Owner")
    c=con(); c.execute("insert into photos(title,category,price,creator,image,approved) values(?,?,?,?,?,0)",(request.form["title"],request.form["category"],float(request.form.get("price",0)),creator,request.form["image"])); c.commit(); c.close()
    flash("Submitted for owner approval."); return redirect(url_for("home"))

if __name__=="__main__": init(); app.run(debug=True)
