#!/usr/bin/env python3
"""
Hot Axle Monitoring System — Raspberry Pi
480x320 SPI TFT

Pi  → "TEMP,<id>\n"
GW  → sets D6/D7/D8 CTRL pins to coach ID
Coach sees match → reads DS18B20 (850ms) → ready
GW  → Wire.requestFrom after 1000ms → gets 7 bytes
GW  → "<left>,<id>,<right>,<temp>\n"  or  "ERROR\n"
Pi  → draws/updates coach box
"""

import serial, threading, time, sys
import tkinter as tk
from tkinter import font as tkfont

PORT     = "/dev/ttyUSB0"
BAUD     = 9600
ALL_IDS  = [0, 1, 2, 3, 4]
REPROBE  = 30
W, H     = 480, 320

# Must be longer than gateway CONV_WAIT (1000ms) + I2C + serial latency
SERIAL_TIMEOUT = 4.0

TNORM, TWARN = 30.0, 40.0

cBG="#0A0A0F"; cPANEL="#12121A"; cHDR="#0D1B2A"
cACCENT="#1E90FF"; cOK="#00E676"; cWARN="#FFD600"
cCRIT="#FF1744"; cNONE="#444455"; cDIM="#334455"
cDK="#0A0A0F"; cLT="#E0E0E0"; cARR="#1E90FF"; cGW="#A78BFA"

class Node:
    def __init__(self, cid, left, right):
        self.cid=cid; self.left=left; self.right=right
        self.temp=None; self.status="WAIT"; self.next=None

    def update(self, temp):
        self.temp=temp
        if   temp < TNORM: self.status="NORMAL"
        elif temp < TWARN: self.status="WARNING"
        else:              self.status="CRITICAL"

    @property
    def color(self):
        return {"NORMAL":cOK,"WARNING":cWARN,"CRITICAL":cCRIT}.get(self.status,cNONE)

    @property
    def tstr(self):
        return f"{self.temp:.1f}°C" if self.temp is not None else "---"


class Monitor(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)
        self._port=port; self._ser=None
        self._lock=threading.Lock()
        self._nodes=[]; self.msg="Connecting..."
        self._last_probe=0.0

    def nodes(self):
        with self._lock: return list(self._nodes)

    def run(self):
        while True:
            try:
                self._connect()
                self._loop()
            except Exception as e:
                self.msg=f"Reconnecting... {e}"
                try: self._ser and self._ser.close()
                except: pass
                time.sleep(3)

    def _connect(self):
        self.msg=f"Connecting {self._port}..."
        self._ser=serial.Serial(self._port, BAUD, timeout=SERIAL_TIMEOUT)
        time.sleep(2)
        self._ser.reset_input_buffer()
        self.msg="Waiting for READY..."
        t=time.time()
        while time.time()-t < 20:
            raw=self._ser.readline()
            if not raw: continue
            line=raw.decode("utf-8",errors="ignore").strip()
            if line=="READY":
                self.msg="Connected — probing coaches..."
                return
        raise ConnectionError("No READY from gateway")

    def _loop(self):
        while True:
            if time.time()-self._last_probe >= REPROBE:
                self._probe()
                self._last_probe=time.time()
            for n in self.nodes():
                r=self._ask(n.cid)
                if r: n.update(r[3])
            if not self.nodes():
                self.msg="No coaches found — retrying..."
                time.sleep(2)

    def _probe(self):
        self.msg="Probing..."
        found=[]
        for cid in ALL_IDS:
            r=self._ask(cid)
            if not r: continue
            left,curr,right,temp=r
            nd=Node(curr,left,right)
            nd.update(temp)
            found.append(nd)
        found.sort(key=lambda n:n.cid)
        for i,n in enumerate(found):
            n.next=found[i+1] if i+1<len(found) else None
        with self._lock: self._nodes=found
        chain=" → ".join(f"C{n.cid}" for n in found)
        self.msg=f"Active: {chain}" if found else "No coaches found"

    def _ask(self, cid):
        try:
            self._ser.reset_input_buffer()
            self._ser.write(f"TEMP,{cid}\n".encode())
            self._ser.flush()
            raw=self._ser.readline()
            if not raw: return None
            line=raw.decode("utf-8",errors="ignore").strip()
            if not line or line=="ERROR": return None
            p=line.split(",")
            if len(p)!=4: return None
            return int(p[0]),int(p[1]),int(p[2]),float(p[3])
        except: return None


class GUI:
    MS=500

    def __init__(self, mon):
        self.mon=mon
        r=tk.Tk()
        r.title("Hot Axle Monitor")
        r.geometry(f"{W}x{H}+0+0")
        r.resizable(False,False)
        r.configure(bg=cBG)
        r.overrideredirect(True)
        try: r.attributes("-zoomed",True)
        except: pass
        self.r=r

        fB=lambda s:tkfont.Font(family="DejaVu Sans Mono",size=s,weight="bold")
        fN=lambda s:tkfont.Font(family="DejaVu Sans",size=s)
        fW=lambda s:tkfont.Font(family="DejaVu Sans",size=s,weight="bold")
        self.fHdr=fW(10); self.fSub=fN(7)
        self.fID=fB(9);   self.fTmp=fB(15)
        self.fStat=fW(7); self.fPtr=fB(6); self.fLeg=fN(7)

        self._build()
        r.after(self.MS, self._tick)

    def _build(self):
        h=tk.Frame(self.r,bg=cHDR,height=36)
        h.place(x=0,y=0,width=W)
        tk.Label(h,text="HOT AXLE MONITORING SYSTEM",
                 font=self.fHdr,bg=cHDR,fg=cACCENT).place(x=8,y=3)
        tk.Label(h,text="CTRL D6/D7/D8  ·  I2C SDA/SCL  ·  sorted ascending",
                 font=self.fSub,bg=cHDR,fg=cDIM).place(x=8,y=21)
        self.lClock=tk.Label(h,text="",font=self.fSub,bg=cHDR,fg=cDIM)
        self.lClock.place(x=390,y=3)

        self.cv=tk.Canvas(self.r,width=W,height=232,bg=cPANEL,highlightthickness=0)
        self.cv.place(x=0,y=36)

        f=tk.Frame(self.r,bg=cHDR,height=52)
        f.place(x=0,y=268,width=W)
        lx=6
        for col,txt in [(cOK,"<30° Normal"),(cWARN,"30-40° Warn"),
                        (cCRIT,">40° Critical"),(cNONE,"No data")]:
            tk.Label(f,text="●",fg=col,bg=cHDR,font=self.fLeg).place(x=lx,y=4)
            tk.Label(f,text=txt,fg=cLT,bg=cHDR,font=self.fLeg).place(x=lx+13,y=4)
            lx+=118
        self.lAlert=tk.Label(f,text="",font=self.fLeg,bg=cHDR,fg=cLT,
                             wraplength=464,justify="left")
        self.lAlert.place(x=6,y=26)

    def _tick(self):
        self._draw()
        self._footer()
        self.lClock.config(text=time.strftime("%H:%M:%S"))
        self.r.after(self.MS,self._tick)

    def _draw(self):
        cv=self.cv; cv.delete("all")
        nodes=self.mon.nodes()
        if not nodes:
            cv.create_text(W//2,116,text=self.mon.msg,font=self.fID,fill=cDIM)
            return

        n=len(nodes)
        NW=min(76,(W-20)//n-10)
        NH=116
        GAP=max(8,(W-10-n*NW)//max(n-1,1))
        TOT=n*NW+max(n-1,0)*GAP
        sx=(W-TOT)//2; cy=116

        for i,nd in enumerate(nodes):
            x=sx+i*(NW+GAP); cx=x+NW//2
            gw=(nd.cid==0)
            cv.create_rectangle(x+3,cy-NH//2+3,x+NW+3,cy+NH//2+3,fill="#000",outline="")
            cv.create_rectangle(x,cy-NH//2,x+NW,cy+NH//2,
                                fill=nd.color,outline=cGW if gw else "white",
                                width=3 if gw else 2)
            cv.create_text(cx,cy-NH//2+13,
                           text=f"C{nd.cid}"+(" GW" if gw else ""),
                           font=self.fID,fill=cDK)
            cv.create_line(x+4,cy-NH//2+24,x+NW-4,cy-NH//2+24,fill=cDK)
            cv.create_text(cx,cy-4,text=nd.tstr,font=self.fTmp,fill=cDK)
            cv.create_text(cx,cy+NH//2-22,text=nd.status,font=self.fStat,fill=cDK)
            lp=f"←{nd.left}"  if nd.left >=0 else "←NULL"
            rp=f"{nd.right}→" if nd.right>=0 else "NULL→"
            cv.create_text(x+4,   cy+NH//2-9,text=lp,font=self.fPtr,fill="#334455",anchor="w")
            cv.create_text(x+NW-4,cy+NH//2-9,text=rp,font=self.fPtr,fill="#334455",anchor="e")
            if i<n-1:
                ax=x+NW; ex=ax+GAP
                cv.create_line(ax,cy,ex,cy,arrow=tk.LAST,fill=cARR,width=2)
                cv.create_text((ax+ex)//2,cy-10,text="next",font=self.fPtr,fill=cARR)

        cv.create_text(sx-4,    cy,text="NULL",font=self.fPtr,fill=cDIM,anchor="e")
        cv.create_text(sx+TOT+4,cy,text="NULL",font=self.fPtr,fill=cDIM,anchor="w")

    def _footer(self):
        nodes=self.mon.nodes()
        crit=[n for n in nodes if n.status=="CRITICAL"]
        warn=[n for n in nodes if n.status=="WARNING"]
        if crit:
            ids=" ".join(f"C{n.cid}" for n in crit)
            txt,fg=f"⚠ CRITICAL HOT AXLE — {ids}",cCRIT
        elif warn:
            ids=" ".join(f"C{n.cid}" for n in warn)
            txt,fg=f"⚠ Warning — {ids}",cWARN
        elif nodes:
            ch=" → ".join(f"C{n.cid}" for n in nodes)
            txt,fg=f"✔ All normal  |  {ch}",cOK
        else:
            txt,fg=self.mon.msg,cDIM
        self.lAlert.config(text=txt,fg=fg)

    def run(self): self.r.mainloop()

if __name__=="__main__":
    port=sys.argv[1] if len(sys.argv)>1 else PORT
    print(f"Hot Axle Monitor | {port} | {BAUD} baud")
    m=Monitor(port); m.start()
    GUI(m).run()
