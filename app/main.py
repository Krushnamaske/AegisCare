import os, math, secrets, hashlib, hmac, base64, asyncio, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import jwt, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, desc, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Mapped, mapped_column, Session

load_dotenv()
SECRET=os.getenv("SECRET_KEY","dev-only-change-me")
BASE_DIR=Path(__file__).resolve().parent.parent
DBURL=os.getenv("DATABASE_URL","").strip() or f"sqlite:///{BASE_DIR / 'aegiscare.db'}"
if DBURL.startswith("postgres://"):
 DBURL=DBURL.replace("postgres://","postgresql+psycopg://",1)
elif DBURL.startswith("postgresql://"):
 DBURL=DBURL.replace("postgresql://","postgresql+psycopg://",1)
YOLO_ON=os.getenv("ENABLE_YOLO","false").lower()=="true"
YOLO_MODEL=os.getenv("YOLO_MODEL","yolov8n.pt")
MAX_MB=int(os.getenv("MAX_UPLOAD_MB","8"))
UPLOAD=str(BASE_DIR / "uploads"); Path(UPLOAD).mkdir(parents=True,exist_ok=True)
engine=create_engine(DBURL,connect_args={"check_same_thread":False} if DBURL.startswith("sqlite") else {},pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase): pass
def hash_password(password:str)->str:
 salt=secrets.token_bytes(16)
 rounds=310000
 digest=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,rounds)
 return "pbkdf2_sha256${}${}${}".format(rounds,base64.urlsafe_b64encode(salt).decode(),base64.urlsafe_b64encode(digest).decode())
def verify_password(password:str,stored:str)->bool:
 try:
  if stored.startswith("pbkdf2_sha256$"):
   _,rounds,salt,digest=stored.split("$",3)
   actual=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),base64.urlsafe_b64decode(salt),int(rounds))
   return hmac.compare_digest(base64.urlsafe_b64encode(actual).decode(),digest)
  # Optional compatibility for older demo databases created with passlib/bcrypt.
  from passlib.context import CryptContext
  return CryptContext(schemes=["bcrypt"],deprecated="auto").verify(password,stored)
 except Exception:return False
def now(): return datetime.now(timezone.utc)
class User(Base):
 __tablename__="users"
 id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120)); email:Mapped[str]=mapped_column(String(255),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(255)); role:Mapped[str]=mapped_column(String(30)); entity_id:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)
class Hospital(Base):
 __tablename__="hospitals"
 id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(180)); address:Mapped[str]=mapped_column(String(300),default=""); latitude:Mapped[float]=mapped_column(Float); longitude:Mapped[float]=mapped_column(Float); phone:Mapped[str]=mapped_column(String(40),default=""); emergency_open:Mapped[bool]=mapped_column(Boolean,default=True); trauma_capable:Mapped[bool]=mapped_column(Boolean,default=False); surgery:Mapped[bool]=mapped_column(Boolean,default=False); icu_total:Mapped[int]=mapped_column(Integer,default=0); icu_occupied:Mapped[int]=mapped_column(Integer,default=0); beds_total:Mapped[int]=mapped_column(Integer,default=0); beds_occupied:Mapped[int]=mapped_column(Integer,default=0); ventilators_available:Mapped[int]=mapped_column(Integer,default=0); blood_bank:Mapped[bool]=mapped_column(Boolean,default=False); notes:Mapped[str]=mapped_column(Text,default=""); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class Ambulance(Base):
 __tablename__="ambulances"
 id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120)); driver_name:Mapped[str]=mapped_column(String(120)); latitude:Mapped[float]=mapped_column(Float); longitude:Mapped[float]=mapped_column(Float); status:Mapped[str]=mapped_column(String(20),default="Available",index=True); phone:Mapped[str]=mapped_column(String(40),default=""); last_location_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Incident(Base):
 __tablename__="incidents"
 id:Mapped[int]=mapped_column(primary_key=True); reporter_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True); image_uri:Mapped[str]=mapped_column(String(500),default=""); latitude:Mapped[float]=mapped_column(Float); longitude:Mapped[float]=mapped_column(Float); description:Mapped[str]=mapped_column(Text,default=""); ai_summary:Mapped[str]=mapped_column(Text,default=""); priority_score:Mapped[int]=mapped_column(Integer,default=0); priority_level:Mapped[str]=mapped_column(String(20),default="Medium"); status:Mapped[str]=mapped_column(String(40),default="Reported",index=True); selected_hospital_id:Mapped[Optional[int]]=mapped_column(ForeignKey("hospitals.id"),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Dispatch(Base):
 __tablename__="dispatches"
 id:Mapped[int]=mapped_column(primary_key=True); incident_id:Mapped[int]=mapped_column(ForeignKey("incidents.id"),index=True); ambulance_id:Mapped[int]=mapped_column(ForeignKey("ambulances.id")); hospital_id:Mapped[Optional[int]]=mapped_column(ForeignKey("hospitals.id"),nullable=True); status:Mapped[str]=mapped_column(String(30),default="Pending",index=True); distance_km:Mapped[float]=mapped_column(Float,default=0); eta_minutes:Mapped[int]=mapped_column(Integer,default=0); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); responded_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
class Alert(Base):
 __tablename__="alerts"
 id:Mapped[int]=mapped_column(primary_key=True); incident_id:Mapped[int]=mapped_column(ForeignKey("incidents.id"),index=True); recipient_role:Mapped[str]=mapped_column(String(30)); recipient_id:Mapped[Optional[int]]=mapped_column(Integer,nullable=True); alert_type:Mapped[str]=mapped_column(String(50)); message:Mapped[str]=mapped_column(Text); delivery_status:Mapped[str]=mapped_column(String(30),default="Saved"); acknowledged_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
def get_db():
 db=SessionLocal()
 try: yield db
 finally: db.close()
def token(u): return jwt.encode({"sub":str(u.id),"role":u.role,"exp":now()+timedelta(hours=12)},SECRET,algorithm="HS256")
def user_dep(request:Request,db:Session=Depends(get_db)):
 t=request.cookies.get("access_token") or request.headers.get("authorization","").removeprefix("Bearer ").strip()
 if not t: raise HTTPException(401,"Please log in.")
 try: uid=int(jwt.decode(t,SECRET,algorithms=["HS256"])["sub"])
 except Exception: raise HTTPException(401,"Session expired; log in again.")
 u=db.get(User,uid)
 if not u: raise HTTPException(401,"User not found.")
 return u
def roles(*allowed):
 def dep(u:User=Depends(user_dep)):
  if u.role not in allowed: raise HTTPException(403,"Your role cannot perform this action.")
  return u
 return dep
def km(a,b,c,d):
 r=6371; p1,p2=math.radians(a),math.radians(c); dp=math.radians(c-a); dl=math.radians(d-b)
 z=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 2*r*math.asin(min(1,math.sqrt(z)))
def eta(d): return max(1,round(d/25*60))
_yolo=None
def analyze(path,description):
 global _yolo
 detections=[]; warning="Image model disabled; score uses the incident description only."
 if YOLO_ON and path:
  try:
   from ultralytics import YOLO
   if _yolo is None: _yolo=YOLO(YOLO_MODEL)
   for r in _yolo(path,verbose=False):
    for box in r.boxes:
     conf=float(box.conf[0].item())
     if conf>=.50:detections.append({"label":r.names[int(box.cls[0].item())],"confidence":round(conf,3)})
   warning="Generic object detections are supporting evidence only; they do not identify injuries or diagnose severity."
  except Exception as e:warning=f"Image model unavailable ({type(e).__name__}); description-only scoring used."
 t=(description or "").lower();score=0;cues=[]
 def negated(phrase):
  return bool(re.search(r"\b(?:no|not|without|never)\s+(?:\w+\s+){0,2}"+re.escape(phrase)+r"\b",t))
 # Use the strongest phrase in each evidence group, rather than adding synonyms
 # together. This reduces accidental score inflation from repeated wording.
 life_threat=[("no pulse",95),("not breathing",90),("unconscious",85),("heavy bleeding",80),("severe bleeding",75),("trapped",70)]
 hit=[(phrase,points) for phrase,points in life_threat if phrase in t]
 if hit:
  phrase,points=max(hit,key=lambda x:x[1]);score+=points;cues.append(f"{phrase} (+{points})")
 casualty_terms=["multiple injured","multiple casualties","several injured","many injured"]
 if any(x in t for x in casualty_terms):score+=25;cues.append("multiple casualties (+25)")
 severe_terms=[("head injury",22),("chest injury",22),("fracture",20),("broken bone",20),("internal injury",25),("deep wound",20)]
 hit=[(phrase,points) for phrase,points in severe_terms if phrase in t and not negated(phrase)]
 if hit:
  phrase,points=max(hit,key=lambda x:x[1]);score+=points;cues.append(f"{phrase} (+{points})")
 injury_terms=["injured","bleeding","wound","pain"]
 if any(x in t and not negated(x) for x in injury_terms):score+=12;cues.append("injury symptom reported (+12)")
 context_terms=["accident","crash","collision","road accident","vehicle hit"]
 if any(x in t and not negated(x) for x in context_terms):score+=8;cues.append("accident context (+8)")
 if any(x in t for x in ["child","infant","baby"]):score+=5;cues.append("child/infant mentioned (+5)")
 labels={x["label"].lower() for x in detections};vehicles={"car","truck","bus","motorcycle","bicycle"}
 if "person" in labels and labels.intersection(vehicles):score+=5;cues.append("person and vehicle objects detected (+5)")
 if any(x in labels for x in ["fire","smoke"]):score+=5;cues.append("fire/smoke object detected (+5)")
 score=min(score,100);level="Critical" if score>=85 else "High" if score>=65 else "Medium" if score>=35 else "Low"
 confidence="Low" if not description.strip() else ("Medium" if not detections else "Medium — generic objects are not clinical evidence")
 summary=(f"Advisory triage score: {score}/100 ({level}). Evidence: {', '.join(cues) if cues else 'No high-risk phrases or supported visual cues detected'}. "
          f"Scoring confidence: {confidence}. {warning} This transparent rule-based score is not clinically validated and cannot confirm actual injury severity; a human responder must verify it.")
 return score,level,summary,detections

def required_facilities(description,score):
 t=(description or "").lower()
 trauma=any(k in t for k in ["accident","crash","collision","road","vehicle","bike","motorcycle","truck","bus","fracture","trapped"])
 critical=score>=65 or any(k in t for k in ["unconscious","not breathing","no pulse","heavy bleeding","severe bleeding"])
 surgery=any(k in t for k in ["trapped","fracture","broken bone","deep wound","internal injury"])
 ventilator=any(k in t for k in ["not breathing","breathing difficulty","respiratory"])
 return {"trauma":trauma,"icu":critical,"surgery":surgery,"ventilator":ventilator,"bed":True}

def hospital_eligible(h,req):
 return (h.emergency_open and (not req["trauma"] or h.trauma_capable) and
         (not req["icu"] or h.icu_total>h.icu_occupied) and
         (not req["surgery"] or h.surgery) and
         (not req["ventilator"] or h.ventilators_available>0) and
         (not req["bed"] or h.beds_total>h.beds_occupied))

async def route(a,b,c,d):
 # OSRM public demo routing: coordinates are longitude,latitude in the URL.
 # This returns road-network distance and duration; it does not include live traffic.
 try:
  async with httpx.AsyncClient(timeout=4) as cl:
   url=f"https://router.project-osrm.org/route/v1/driving/{b},{a};{d},{c}"
   r=await cl.get(url,params={"overview":"false","steps":"false"},headers={"User-Agent":"AegisCare-Hackathon-Demo/1.0"})
   r.raise_for_status(); data=r.json()
   if data.get("code")!="Ok" or not data.get("routes"): return None
   x=data["routes"][0]
   return {"distance_km":x["distance"]/1000,"eta_minutes":max(1,round(x["duration"]/60)),"source":"OSRM/OpenStreetMap road estimate"}
 except Exception:return None
AMBULANCE_RESPONSE_SECONDS=int(os.getenv("AMBULANCE_RESPONSE_SECONDS","45"))
HOSPITAL_RESPONSE_SECONDS=int(os.getenv("HOSPITAL_RESPONSE_SECONDS","90"))

async def next_ambulance(db,inc):
 used=[x.ambulance_id for x in db.query(Dispatch).filter(Dispatch.incident_id==inc.id).all()]
 candidates=db.query(Ambulance).filter(Ambulance.status=="Available",Ambulance.id.not_in(used)).all()
 ranked=[]
 for a in candidates:
  rt=await route(a.latitude,a.longitude,inc.latitude,inc.longitude)
  dist=rt["distance_km"] if rt else km(a.latitude,a.longitude,inc.latitude,inc.longitude)
  travel=rt["eta_minutes"] if rt else eta(dist)
  ranked.append((travel,dist,a,rt is not None))
 ranked.sort(key=lambda x:(x[0],x[1]))
 if not ranked:
  inc.status="No available ambulance accepted";db.commit();return None
 travel,dist,a,has_road=ranked[0]
 a.status="Dispatched"
 d=Dispatch(incident_id=inc.id,ambulance_id=a.id,hospital_id=inc.selected_hospital_id,status="Pending",distance_km=dist,eta_minutes=travel)
 db.add(d);db.flush()
 db.add(Alert(incident_id=inc.id,recipient_role="ambulance",recipient_id=a.id,alert_type="dispatch_request",message=f"Dispatch request for incident #{inc.id}, {inc.priority_level} priority. Road ETA {travel} min ({'OSRM road estimate' if has_road else 'straight-line fallback'}). Image: {inc.image_uri or 'No image attached'}"))
 inc.status=f"Awaiting ambulance #{a.id} response"
 db.commit();db.refresh(d)
 await hub.send({"type":"dispatch_request","dispatch_id":d.id,"ambulance_id":a.id,"message":f"New dispatch request for your ambulance #{a.id}"},target_role="ambulance",target_id=a.id)
 return d

async def next_hospital(db,inc,exclude_ids=None):
 exclude_ids=set(exclude_ids or [])
 req=required_facilities(inc.description,inc.priority_score)
 hospitals=db.query(Hospital).filter(Hospital.emergency_open==True).all()
 ranked=[]
 for h in hospitals:
  if h.id in exclude_ids or not hospital_eligible(h,req):continue
  rt=await route(inc.latitude,inc.longitude,h.latitude,h.longitude)
  dist=rt["distance_km"] if rt else km(inc.latitude,inc.longitude,h.latitude,h.longitude)
  travel=rt["eta_minutes"] if rt else eta(dist)
  ranked.append((travel,dist,h,rt is not None))
 ranked.sort(key=lambda x:(x[0],x[1]))
 if not ranked:return None
 travel,dist,h,has_road=ranked[0]
 inc.selected_hospital_id=h.id
 inc.status=f"Awaiting hospital #{h.id} response"
 for pending_dispatch in db.query(Dispatch).filter(Dispatch.incident_id==inc.id,Dispatch.status.in_(["Pending","Accepted","En route","Arrived","Transporting"])).all():
  pending_dispatch.hospital_id=h.id
 db.add(Alert(incident_id=inc.id,recipient_role="hospital",recipient_id=h.id,alert_type="hospital_prealert",message=f"Primary facility request for incident #{inc.id}. Priority {inc.priority_level} ({inc.priority_score}/100). Estimated arrival {travel} min. Required capabilities: {', '.join(k for k,v in req.items() if v)}. Image URI: {inc.image_uri or 'No image attached'}. Please accept or decline promptly."))
 db.commit()
 await hub.send({"type":"hospital_prealert","hospital_id":h.id,"incident_id":inc.id,"message":f"New incident request for your facility: {h.name}"},target_role="hospital",target_id=h.id)
 return {"hospital":h,"eta":travel,"distance":dist,"source":"OSRM road estimate" if has_road else "straight-line fallback estimate","requirements":req}

async def advance_expired_dispatches(db):
 cutoff=now()-timedelta(seconds=AMBULANCE_RESPONSE_SECONDS)
 pending=db.query(Dispatch).filter(Dispatch.status=="Pending").all()
 for d in pending:
  created=d.created_at
  if created and created.tzinfo is None:created=created.replace(tzinfo=timezone.utc)
  if not created or created>cutoff:continue
  inc=db.get(Incident,d.incident_id);a=db.get(Ambulance,d.ambulance_id)
  if not inc or d.status!="Pending":continue
  d.status="Timed out";d.responded_at=now()
  if a and a.status=="Dispatched":a.status="Available"
  db.add(Alert(incident_id=inc.id,recipient_role="admin",recipient_id=None,alert_type="dispatch_timeout",message=f"Ambulance #{d.ambulance_id} did not respond within {AMBULANCE_RESPONSE_SECONDS} seconds."))
  db.commit()
  await next_ambulance(db,inc)

async def advance_expired_hospital_requests(db):
 cutoff=now()-timedelta(seconds=HOSPITAL_RESPONSE_SECONDS)
 pending=db.query(Alert).filter(Alert.recipient_role=="hospital",Alert.alert_type=="hospital_prealert",Alert.delivery_status=="Saved").all()
 for alert in pending:
  created=alert.created_at
  if created and created.tzinfo is None:created=created.replace(tzinfo=timezone.utc)
  if not created or created>cutoff:continue
  inc=db.get(Incident,alert.incident_id)
  if not inc or alert.delivery_status!="Saved":continue
  alert.delivery_status="Timed out";alert.acknowledged_at=now();db.commit()
  tried=[x.recipient_id for x in db.query(Alert).filter(Alert.incident_id==inc.id,Alert.recipient_role=="hospital",Alert.alert_type=="hospital_prealert").all()]
  nxt=await next_hospital(db,inc,tried)
  if not nxt:
   inc.selected_hospital_id=None;inc.status="No eligible hospital accepted";db.commit()

app=FastAPI(title="AegisCare",version="1.0.0")
app.mount("/uploads",StaticFiles(directory=UPLOAD),name="uploads"); app.mount("/static",StaticFiles(directory=str(BASE_DIR / "app" / "static")),name="static")
class Hub:
 def __init__(self):self.clients=[]
 async def connect(self,w,role,entity_id):
  await w.accept();self.clients.append((w,role,entity_id))
 def drop(self,w):
  self.clients=[x for x in self.clients if x[0] is not w]
 async def send(self,msg,target_role=None,target_id=None):
  for w,role,entity_id in list(self.clients):
   if target_role and role not in [target_role,"admin"]:continue
   if target_id is not None and role==target_role and entity_id!=target_id:continue
   try:await w.send_json(msg)
   except Exception:self.drop(w)
hub=Hub()
@app.on_event("startup")
def start():
 Base.metadata.create_all(engine)
 db=SessionLocal()
 try:
  # Seed deterministic local-demo entities and role-specific accounts once.
  if db.query(Hospital).count()==0:
   db.add_all([
    Hospital(name="AegisCare Trauma Centre",address="Pune, Maharashtra",latitude=18.5204,longitude=73.8567,phone="+91-20-4000-1001",emergency_open=True,trauma_capable=True,surgery=True,icu_total=12,icu_occupied=4,beds_total=80,beds_occupied=32,ventilators_available=5,blood_bank=True,notes="Demo facility data — verify before operational use."),
    Hospital(name="City Multispecialty Hospital",address="Shivajinagar, Pune",latitude=18.5308,longitude=73.8475,phone="+91-20-4000-1002",emergency_open=True,trauma_capable=True,surgery=True,icu_total=8,icu_occupied=3,beds_total=60,beds_occupied=28,ventilators_available=3,blood_bank=True,notes="Demo facility data — verify before operational use."),
    Hospital(name="East Pune Emergency Hospital",address="Kharadi, Pune",latitude=18.5515,longitude=73.9348,phone="+91-20-4000-1003",emergency_open=True,trauma_capable=False,surgery=True,icu_total=6,icu_occupied=2,beds_total=45,beds_occupied=20,ventilators_available=2,blood_bank=False,notes="Demo facility data — verify before operational use.")
   ]);db.commit()
  if db.query(Ambulance).count()==0:
   db.add_all([
    Ambulance(name="Aegis Ambulance 01",driver_name="Demo Driver One",latitude=18.5160,longitude=73.8500,status="Available",phone="+91-90000-00001"),
    Ambulance(name="Aegis Ambulance 02",driver_name="Demo Driver Two",latitude=18.5350,longitude=73.8600,status="Available",phone="+91-90000-00002"),
    Ambulance(name="Aegis Ambulance 03",driver_name="Demo Driver Three",latitude=18.5480,longitude=73.9200,status="Available",phone="+91-90000-00003")
   ]);db.commit()
  demo=[("Demo Citizen","citizen@aegiscare.demo","reporter",None),("Demo Hospital","hospital@aegiscare.demo","hospital",1),("Demo Ambulance","ambulance@aegiscare.demo","ambulance",1),("Demo Admin","admin@aegiscare.demo","admin",None)]
  for name,email,role,eid in demo:
   if not db.query(User).filter(User.email==email).first():
    db.add(User(name=name,email=email,password_hash=hash_password("AegisDemo!2026"),role=role,entity_id=eid))
  db.flush()
  for h in db.query(Hospital).all():
   email=f"hospital{h.id}@aegiscare.demo"
   if not db.query(User).filter(User.email==email).first():db.add(User(name=f"Demo Hospital {h.id}",email=email,password_hash=hash_password("AegisDemo!2026"),role="hospital",entity_id=h.id))
  for a in db.query(Ambulance).all():
   email=f"ambulance{a.id}@aegiscare.demo"
   if not db.query(User).filter(User.email==email).first():db.add(User(name=f"Demo Ambulance {a.id}",email=email,password_hash=hash_password("AegisDemo!2026"),role="ambulance",entity_id=a.id))
  db.commit()
 finally: db.close()
@app.get("/",response_class=HTMLResponse)
def home():return (BASE_DIR / "app" / "static" / "index.html").read_text(encoding="utf8")
@app.get("/api/health")
def health(db:Session=Depends(get_db)):
 db.execute(text("SELECT 1"))
 return {"status":"ok","database":"connected","time":now().isoformat()}
@app.post("/api/login")
def login(email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
 u=db.query(User).filter(User.email==email.lower().strip()).first()
 if not u or not verify_password(password,u.password_hash):raise HTTPException(401,"Invalid email or password.")
 r=JSONResponse({"ok":True,"name":u.name,"role":u.role,"entity_id":u.entity_id});r.set_cookie("access_token",token(u),httponly=True,samesite="lax",secure=os.getenv("COOKIE_SECURE","false").lower()=="true",max_age=43200);return r
@app.post("/api/register")
def register(name:str=Form(...),email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
 name=name.strip(); email=email.lower().strip()
 if len(name)<2 or len(name)>120: raise HTTPException(422,"Name must be 2–120 characters.")
 if len(password)<10: raise HTTPException(422,"Use a password with at least 10 characters.")
 if db.query(User).filter(User.email==email).first(): raise HTTPException(409,"An account with this email already exists.")
 # Public registration creates reporter accounts only. Hospital/ambulance accounts must be provisioned by an authorized administrator.
 u=User(name=name,email=email,password_hash=hash_password(password),role="reporter")
 db.add(u);db.commit();db.refresh(u)
 r=JSONResponse({"ok":True,"name":u.name,"role":u.role,"message":"Account created. You can now sign in."},status_code=201)
 return r

@app.post("/api/logout")
def logout():
 r=JSONResponse({"ok":True});r.delete_cookie("access_token");return r
@app.get("/api/me")
def me(u:User=Depends(user_dep)):return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"entity_id":u.entity_id}
@app.get("/api/dashboard")
async def dashboard(u:User=Depends(user_dep),db:Session=Depends(get_db)):
 await advance_expired_dispatches(db)
 await advance_expired_hospital_requests(db)
 def dt(x):return x.isoformat() if x else None
 hs=db.query(Hospital).all(); ambs=db.query(Ambulance).all(); ins=db.query(Incident).order_by(desc(Incident.created_at)).limit(40).all(); ds=db.query(Dispatch).order_by(desc(Dispatch.created_at)).limit(40).all(); als=db.query(Alert).order_by(desc(Alert.created_at)).limit(40).all()
 if u.role=="reporter":
  ins=[i for i in ins if i.reporter_id==u.id]
  incident_ids={i.id for i in ins};ds=[d for d in ds if d.incident_id in incident_ids];als=[]
 elif u.role=="hospital" and u.entity_id:
  relevant={a.incident_id for a in db.query(Alert).filter(Alert.recipient_role=="hospital",Alert.recipient_id==u.entity_id).all()}
  ins=[i for i in ins if i.selected_hospital_id==u.entity_id or i.id in relevant]
  incident_ids={i.id for i in ins};ds=[d for d in ds if d.incident_id in incident_ids and d.hospital_id==u.entity_id]
  als=[a for a in als if a.recipient_role=="hospital" and a.recipient_id==u.entity_id]
 elif u.role=="ambulance" and u.entity_id:
  relevant={d.incident_id for d in db.query(Dispatch).filter(Dispatch.ambulance_id==u.entity_id).all()}
  ins=[i for i in ins if i.id in relevant]
  ds=[d for d in ds if d.ambulance_id==u.entity_id]
  als=[a for a in als if a.recipient_role=="ambulance" and a.recipient_id==u.entity_id]
 return {"user":{"name":u.name,"role":u.role,"entity_id":u.entity_id},
 "hospitals":[{"id":h.id,"name":h.name,"address":h.address,"latitude":h.latitude,"longitude":h.longitude,"phone":h.phone,"emergency_open":h.emergency_open,"trauma_capable":h.trauma_capable,"surgery":h.surgery,"icu_total":h.icu_total,"icu_occupied":h.icu_occupied,"icu_available":max(0,h.icu_total-h.icu_occupied),"beds_total":h.beds_total,"beds_occupied":h.beds_occupied,"beds_available":max(0,h.beds_total-h.beds_occupied),"ventilators_available":h.ventilators_available,"blood_bank":h.blood_bank,"notes":h.notes,"updated_at":dt(h.updated_at)} for h in hs],
 "ambulances":[{"id":a.id,"name":a.name,"driver_name":a.driver_name,"latitude":a.latitude,"longitude":a.longitude,"status":a.status,"last_location_at":dt(a.last_location_at)} for a in ambs],
 "incidents":[{"id":i.id,"latitude":i.latitude,"longitude":i.longitude,"description":i.description,"image_uri":i.image_uri,"priority_score":i.priority_score,"priority_level":i.priority_level,"ai_summary":i.ai_summary,"status":i.status,"selected_hospital_id":i.selected_hospital_id,"created_at":dt(i.created_at)} for i in ins],
 "dispatches":[{"id":d.id,"incident_id":d.incident_id,"ambulance_id":d.ambulance_id,"hospital_id":d.hospital_id,"status":d.status,"distance_km":round(d.distance_km,2),"eta_minutes":d.eta_minutes,"created_at":dt(d.created_at)} for d in ds],
 "alerts":[{"id":a.id,"incident_id":a.incident_id,"recipient_role":a.recipient_role,"recipient_id":a.recipient_id,"alert_type":a.alert_type,"message":a.message,"delivery_status":a.delivery_status,"created_at":dt(a.created_at)} for a in als]}
@app.post("/api/incidents")
async def incident(latitude:float=Form(...),longitude:float=Form(...),description:str=Form(""),image:Optional[UploadFile]=File(None),u:User=Depends(roles("reporter","admin")),db:Session=Depends(get_db)):
 if not(-90<=latitude<=90 and -180<=longitude<=180):raise HTTPException(422,"Invalid coordinates.")
 if not description.strip() and not image:raise HTTPException(422,"Add a description or an incident photo before submitting.")
 uri="";path=None
 if image and image.filename:
  data=await image.read()
  if len(data)>MAX_MB*1024*1024:raise HTTPException(413,f"Image exceeds {MAX_MB} MB.")
  if not image.content_type or not image.content_type.startswith("image/"):raise HTTPException(415,"Upload an image.")
  ext=Path(image.filename).suffix.lower()
  if ext not in [".jpg",".jpeg",".png",".webp"]:ext=".jpg"
  name="incident_"+secrets.token_hex(10)+ext;path=str(Path(UPLOAD)/name);Path(path).write_bytes(data);uri="/uploads/"+name
 score,level,summary,dets=analyze(path,description)
 i=Incident(reporter_id=u.id,image_uri=uri,latitude=latitude,longitude=longitude,description=description[:3000],ai_summary=summary,priority_score=score,priority_level=level,status="Reported")
 db.add(i);db.commit();db.refresh(i)
 hospital=await next_hospital(db,i)
 disp=await next_ambulance(db,i)
 await hub.send({"type":"incident_created","incident_id":i.id,"message":f"Incident #{i.id} saved successfully"},target_role="reporter")
 return {"id":i.id,"priority_score":score,"priority_level":level,"ai_summary":summary,"detections":dets,
 "selected_hospital":{"id":hospital["hospital"].id,"name":hospital["hospital"].name,"eta_minutes":hospital["eta"],"eta_source":hospital["source"],"required_facilities":hospital["requirements"]} if hospital else None,
 "dispatch":{"id":disp.id,"ambulance_id":disp.ambulance_id,"status":disp.status,"eta_minutes":disp.eta_minutes} if disp else None,
 "message":"Incident saved. A single facility-matched hospital and one nearest available ambulance have been contacted; backup escalation is sequential."}

@app.post("/api/dispatches/{did}/respond")
async def respond(did:int,decision:str=Form(...),u:User=Depends(roles("ambulance","admin")),db:Session=Depends(get_db)):
 d=db.get(Dispatch,did)
 if not d:raise HTTPException(404,"Dispatch not found.")
 a=db.get(Ambulance,d.ambulance_id)
 if u.role=="ambulance" and u.entity_id and a.id!=u.entity_id:raise HTTPException(403,"Not assigned to your account.")
 if d.status!="Pending":raise HTTPException(409,"Dispatch is no longer awaiting a response.")
 decision=decision.lower().strip()
 if decision not in ["accept","reject"]:raise HTTPException(422,"Decision must be accept or reject.")
 d.responded_at=now();inc=db.get(Incident,d.incident_id)
 if decision=="accept":
  d.status="Accepted";a.status="Busy";inc.status=f"Ambulance #{a.id} accepted"
  msg=f"{a.name} accepted incident #{inc.id}. No other ambulance will be contacted."
  nxt=None
 else:
  d.status="Rejected";a.status="Available";msg=f"{a.name} declined incident #{inc.id}. Trying the next-nearest available ambulance."
  db.commit();nxt=await next_ambulance(db,inc)
 db.add(Alert(incident_id=inc.id,recipient_role="hospital",recipient_id=inc.selected_hospital_id,alert_type="dispatch_update",message=msg));db.commit()
 await hub.send({"type":"dispatch_update","message":msg},target_role="hospital",target_id=inc.selected_hospital_id)
 return {"ok":True,"status":d.status,"message":msg,"next_dispatch":{"id":nxt.id,"ambulance_id":nxt.ambulance_id,"eta_minutes":nxt.eta_minutes} if nxt else None}

@app.post("/api/hospitals/{hid}/incidents/{iid}/respond")
async def hospital_respond(hid:int,iid:int,decision:str=Form(...),u:User=Depends(roles("hospital","admin")),db:Session=Depends(get_db)):
 h=db.get(Hospital,hid);inc=db.get(Incident,iid)
 if not h or not inc:raise HTTPException(404,"Hospital or incident not found.")
 if u.role=="hospital" and u.entity_id and u.entity_id!=hid:raise HTTPException(403,"This incident request belongs to another hospital.")
 alert=db.query(Alert).filter(Alert.incident_id==iid,Alert.recipient_role=="hospital",Alert.recipient_id==hid,Alert.alert_type=="hospital_prealert").order_by(desc(Alert.created_at)).first()
 if not alert or alert.delivery_status in ["Accepted","Rejected","Timed out"]:raise HTTPException(409,"No pending hospital request for this incident.")
 decision=decision.lower().strip()
 if decision not in ["accept","reject"]:raise HTTPException(422,"Decision must be accept or reject.")
 alert.delivery_status="Accepted" if decision=="accept" else "Rejected";alert.acknowledged_at=now()
 if decision=="accept":inc.selected_hospital_id=hid;inc.status=f"Hospital {h.name} accepted";next_info=None
 else:
  tried=[x.recipient_id for x in db.query(Alert).filter(Alert.incident_id==iid,Alert.recipient_role=="hospital",Alert.alert_type=="hospital_prealert").all()]
  db.commit();next_info=await next_hospital(db,inc,tried)
  if not next_info:inc.selected_hospital_id=None;inc.status="No eligible hospital accepted";db.commit()
 db.commit()
 await hub.send({"type":"hospital_response","message":f"Hospital {h.name} {decision} incident #{iid}."},target_role="reporter")
 return {"ok":True,"message":f"{h.name} {decision} incident #{iid}.","next_hospital":{"id":next_info["hospital"].id,"name":next_info["hospital"].name} if next_info else None}

@app.patch("/api/ambulances/{aid}/status")
def amb_status(aid:int,status:str=Form(...),u:User=Depends(roles("ambulance","admin")),db:Session=Depends(get_db)):
 a=db.get(Ambulance,aid)
 if not a:raise HTTPException(404,"Ambulance not found.")
 if u.role=="ambulance" and u.entity_id and a.id!=u.entity_id:raise HTTPException(403,"Cannot update another ambulance.")
 if status not in ["Available","Busy","Offline"]:raise HTTPException(422,"Invalid status.")
 a.status=status;db.commit();return {"ok":True,"status":status}
@app.post("/api/ambulances/{aid}/location")
def amb_location(aid:int,latitude:float=Form(...),longitude:float=Form(...),u:User=Depends(roles("ambulance","admin")),db:Session=Depends(get_db)):
 a=db.get(Ambulance,aid)
 if not a:raise HTTPException(404,"Ambulance not found.")
 if u.role=="ambulance" and u.entity_id and a.id!=u.entity_id:raise HTTPException(403,"Cannot update another ambulance.")
 if not(-90<=latitude<=90 and -180<=longitude<=180):raise HTTPException(422,"Invalid coordinates.")
 a.latitude=latitude;a.longitude=longitude;a.last_location_at=now();db.commit();return {"ok":True}
@app.patch("/api/hospitals/{hid}")
def hospital_update(hid:int,name:str=Form(...),address:str=Form(""),latitude:float=Form(...),longitude:float=Form(...),phone:str=Form(""),emergency_open:bool=Form(True),trauma_capable:bool=Form(False),surgery:bool=Form(False),icu_total:int=Form(0),icu_occupied:int=Form(0),beds_total:int=Form(0),beds_occupied:int=Form(0),ventilators_available:int=Form(0),blood_bank:bool=Form(False),notes:str=Form(""),u:User=Depends(roles("hospital","admin")),db:Session=Depends(get_db)):
 h=db.get(Hospital,hid)
 if not h:raise HTTPException(404,"Hospital not found.")
 if u.role=="hospital" and u.entity_id and h.id!=u.entity_id:raise HTTPException(403,"Cannot edit another hospital.")
 if min(icu_total,icu_occupied,beds_total,beds_occupied,ventilators_available)<0 or icu_occupied>icu_total or beds_occupied>beds_total:raise HTTPException(422,"Counts must be non-negative and occupied cannot exceed total.")
 if not(-90<=latitude<=90 and -180<=longitude<=180):raise HTTPException(422,"Invalid coordinates.")
 for k,v in locals().copy().items():
  if k in ["name","address","latitude","longitude","phone","emergency_open","trauma_capable","surgery","icu_total","icu_occupied","beds_total","beds_occupied","ventilators_available","blood_bank","notes"]:setattr(h,k,v)
 h.updated_at=now();db.commit();return {"ok":True,"message":"Saved; availability is self-reported and must be verified."}
@app.patch("/api/dispatches/{did}/status")
async def dispatch_status(did:int,status:str=Form(...),u:User=Depends(roles("ambulance","admin")),db:Session=Depends(get_db)):
 d=db.get(Dispatch,did)
 if not d: raise HTTPException(404,"Dispatch not found.")
 a=db.get(Ambulance,d.ambulance_id)
 if u.role=="ambulance" and u.entity_id and a.id!=u.entity_id: raise HTTPException(403,"This dispatch is assigned to another ambulance.")
 allowed={"En route","Arrived","Transporting","Completed"}
 if status not in allowed: raise HTTPException(422,"Invalid dispatch status.")
 if d.status not in ["Accepted","En route","Arrived","Transporting"]: raise HTTPException(409,"Accept this dispatch before updating its progress.")
 d.status=status
 inc=db.get(Incident,d.incident_id)
 inc.status={"En route":"Ambulance en route","Arrived":"Ambulance arrived","Transporting":"Patient being transported","Completed":"Completed"}[status]
 if status=="Completed": a.status="Available"
 db.add(Alert(incident_id=inc.id,recipient_role="hospital",recipient_id=d.hospital_id,alert_type="dispatch_progress",message=f"{a.name}: incident #{inc.id} status updated to {status}."))
 db.commit()
 await hub.send({"type":"dispatch_progress","message":f"{a.name}: incident #{inc.id} — {status}"},target_role="hospital",target_id=inc.selected_hospital_id)
 return {"ok":True,"status":status,"incident_status":inc.status}

@app.post("/api/alerts/{aid}/ack")
def ack(aid:int,u:User=Depends(user_dep),db:Session=Depends(get_db)):
 a=db.get(Alert,aid)
 if not a:raise HTTPException(404,"Alert not found.")
 if u.role not in ["admin",a.recipient_role]:raise HTTPException(403,"Not authorized.")
 if u.role=="hospital" and a.recipient_id is not None and u.entity_id!=a.recipient_id:raise HTTPException(403,"This alert belongs to another hospital.")
 if u.role=="ambulance" and a.recipient_id is not None and u.entity_id!=a.recipient_id:raise HTTPException(403,"This alert belongs to another ambulance.")
 a.delivery_status="Acknowledged";a.acknowledged_at=now();db.commit();return {"ok":True}
@app.websocket("/ws")
async def ws(w:WebSocket):
 t=w.cookies.get("access_token")
 if not t:
  await w.close(code=4401);return
 db=SessionLocal()
 try:
  try:uid=int(jwt.decode(t,SECRET,algorithms=["HS256"])["sub"])
  except Exception:await w.close(code=4401);return
  user=db.get(User,uid)
  if not user:await w.close(code=4401);return
  await hub.connect(w,user.role,user.entity_id)
 finally:db.close()
 try:
  while True:await w.receive_text()
 except WebSocketDisconnect:hub.drop(w)
 except Exception:hub.drop(w)
