#!/usr/bin/env python3

import datetime
import smtplib
import csv
import os
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from serpapi import GoogleSearch
from ics import Calendar, Event

# ==========================================
# USER CONFIGURATION
# ==========================================
SERPAPI_KEY = "USER_SERPAPI_KEY" # can get for free (100 searches a month)
PUSHOVER_USER_KEY = "PUSHOVER_USER_KEY" # free trail or once off $5
PUSHOVER_API_TOKEN = "USER_PUSHOVER_API_TOKEN"

EMAIL_SENDER = "user_email@gmail.com"
EMAIL_APP_PASSWORD = "user_app_password" # not your email log in password
EMAIL_RECEIVER = "user_email@gmail.com"

WORK_AIRPORT = "SYD"
MONTHS_TO_SCAN = 3  # Safely back up to 3 months
GOOD_PRICE_THRESHOLD = 380
CSV_FILE = "commute_matrix_data.csv"

# Ground Costs
COSTS = {
    "AVV_PARKING": 85,
    "MEL_PARKING": 88,
    "MEL_LIFT": 0
}

# ==========================================
# CORE FUNCTIONS
# ==========================================

def get_commute_mondays(months_ahead):
    """Finds the 'Anchor Monday' for the first week of future months."""
    mondays = []
    today = datetime.date.today()
    for i in range(1, months_ahead + 1):
        future = today + datetime.timedelta(days=30 * i)
        first_of_month = future.replace(day=1)
        days_ahead = 0 - first_of_month.weekday()
        if days_ahead < 0: days_ahead += 7
        mon = first_of_month + datetime.timedelta(days=days_ahead)
        mondays.append(mon)
    return mondays

def check_flight(origin, dest, date, time_window=None):
    """
    Checks flight price with time filtering.
    """
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": date.strftime("%Y-%m-%d"),
        "currency": "AUD",
        "hl": "en",
        "type": "2"
    }
    
    # Apply Time Filters (Best effort parameter)
    if time_window:
        params["departure_time"] = time_window

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        best_flights = results.get("best_flights", [])
        if not best_flights: return 9999, "None", ""
        
        flight = best_flights[0]
        price = flight.get("price", 9999)
        airline = flight["flights"][0]["airline"]
        
        link = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{date}"
        return price, airline, link
    except:
        return 9999, "Error", ""

def log_data(row):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        fields = ["scanned_at", "anchor_week", "itin_type", "dept_date", "return_date", "airport", "total_cost"]
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists: writer.writeheader()
        writer.writerow(row)

def create_ics_file(dept, ret, trip_name):
    c = Calendar()
    e = Event()
    e.name = f"✈️ SYD Commute ({trip_name})"
    e.begin = f"{dept.strftime('%Y-%m-%d')} 06:00:00"
    e.end = f"{ret.strftime('%Y-%m-%d')} 20:00:00"
    c.events.add(e)
    filename = f"Trip_{dept.strftime('%b%d')}.ics"
    with open(filename, 'w') as f: f.writelines(c.serialize_iter())
    return filename

def send_push_notification(message, url=None):
    payload = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message,
        "title": "Commute Matrix 📊"
    }
    if url: payload["url"] = url
    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload)
    except:
        pass

def analyze_matrix(anchor_monday):
    """
    The Optimized Matrix Scanner:
    Departures: Mon (0), Tue (+1)
    Returns: Thu Night (+3), Fri (+4), Sat Morn (+5)
    """
    week_results = {
        "anchor": anchor_monday, 
        "best_option": None, 
        "all_options": []
    }
    
    # --- MATRIX DEFINITION ---
    dept_offsets = [
        (0, "Mon"), 
        (1, "Tue")
    ]
    return_offsets = [
        (3, "Thu Night", "1600-2359"), 
        (4, "Fri", None), 
        (5, "Sat Morn", "0600-1200")
    ]
    
    print(f"   Analyzing {anchor_monday.strftime('%b')} Matrix: 2 Dept x 3 Ret...")

    # Loop Matrix
    for d_off, d_label in dept_offsets:
        dept_date = anchor_monday + datetime.timedelta(days=d_off)
        
        for r_off, r_label, time_filter in return_offsets:
            ret_date = anchor_monday + datetime.timedelta(days=r_off)
            
            # Check Both Airports
            for airport in ["AVV", "MEL"]:
                
                # 1. Get Prices
                p_out, air_out, link = check_flight(airport, WORK_AIRPORT, dept_date)
                p_in, _, _ = check_flight(WORK_AIRPORT, airport, ret_date, time_filter)
                
                flight_cost = p_out + p_in
                
                # 2. Calculate Total (Ground Logic)
                if airport == "AVV":
                    ground = COSTS["AVV_PARKING"]
                else:
                    # Assume Lift for MEL in matrix to show best potential
                    ground = COSTS["MEL_LIFT"] 

                total = flight_cost + ground
                
                # 3. Store Result
                itin_type = f"{d_label}-{r_label}"
                entry = {
                    "type": f"{airport} ({itin_type})",
                    "airline": air_out,
                    "dept": dept_date,
                    "ret": ret_date,
                    "flight": flight_cost,
                    "total": total,
                    "link": link,
                    "airport_code": airport
                }
                
                week_results["all_options"].append(entry)
                
                # 4. Log to CSV
                log_data({
                    "scanned_at": datetime.datetime.now(),
                    "anchor_week": anchor_monday,
                    "itin_type": itin_type,
                    "dept_date": dept_date,
                    "return_date": ret_date,
                    "airport": airport,
                    "total_cost": total
                })

    # Find the single best winner
    week_results["all_options"].sort(key=lambda x: x["total"])
    week_results["best_option"] = week_results["all_options"][0]
    
    return week_results

def send_email_report(weeks):
    msg = MIMEMultipart()
    msg['Subject'] = "Commute Matrix Report (Mon/Tue Options)"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    html = "<html><body style='font-family: Helvetica, Arial;'><h2>✈️ Commute Matrix Analysis</h2>"
    files_to_attach = []
    
    deal_count = 0

    for w in weeks:
        best = w["best_option"]
        runner_up = w["all_options"][1] if len(w["all_options"]) > 1 else None
        
        # Color Code
        color = "#27ae60" if best["total"] < GOOD_PRICE_THRESHOLD else "#2c3e50"
        
        # Generate ICS for winner if price is good
        if best["total"] < GOOD_PRICE_THRESHOLD:
            deal_count += 1
            ics = create_ics_file(best["dept"], best["ret"], best["type"])
            files_to_attach.append(ics)
            
        html += f"""
        <div style="border:1px solid #ddd; padding:15px; margin-bottom:20px; border-radius:8px;">
            <h3 style="margin-top:0; border-bottom:1px solid #eee; padding-bottom:5px;">
                Week of {w['anchor'].strftime('%d %b')}
            </h3>
            
            <div style="background-color:#f4f6f7; padding:15px; border-left: 5px solid {color};">
                <span style="font-size:0.9em; color:#7f8c8d; text-transform:uppercase; letter-spacing:1px;">Best Option</span><br>
                <strong style="font-size:1.2em;">{best['type']}</strong><br>
                <div style="margin:5px 0;">
                   🛫 {best['dept'].strftime('%a %d')} &nbsp; 🛬 {best['ret'].strftime('%a %d')}
                </div>
                Flight: ${best['flight']} | Total Est: <strong>${best['total']}</strong><br>
                <a href="{best['link']}" style="display:inline-block; margin-top:10px; color:#2980b9; text-decoration:none;">🔗 Direct Booking Link</a>
            </div>
            """
            
        if runner_up:
            html += f"""
            <div style="margin-top:10px; font-size:0.9em; color:#666; padding-left:10px;">
                🥈 Runner Up: {runner_up['type']} (${runner_up['total']})
            </div>
            """
        
        html += "</div>"

    html += "</body></html>"
    msg.attach(MIMEText(html, 'html'))

    # Attach ICS
    for f in files_to_attach:
        with open(f, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {f}")
        msg.attach(part)

    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(EMAIL_SENDER, EMAIL_APP_PASSWORD)
        s.send_message(msg)
        s.quit()
        print("✅ Matrix Report Sent.")
        
        # Send Push
        push_msg = f"Matrix Scan Complete. {deal_count} deals found below ${GOOD_PRICE_THRESHOLD}."
        send_push_notification(push_msg)
        
    except Exception as e:
        print(f"❌ Email Failed: {e}")
        
    for f in files_to_attach: os.remove(f)

# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    print("🤖 Commute Matrix (v5.1) Initialized...")
    print(f"   Scanning {MONTHS_TO_SCAN} months ahead.")
    print("   Departures: Mon / Tue")
    print("   Returns: Thu (PM) / Fri / Sat (AM)")
    
    anchors = get_commute_mondays(MONTHS_TO_SCAN)
    reports = []
    
    for mon in anchors:
        reports.append(analyze_matrix(mon))
        
    send_email_report(reports)
