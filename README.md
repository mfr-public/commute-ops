# CommuteOps ✈️

**A Python-based RPA agent to optimise recurring commuter travel between Melbourne (AVV/MEL) and Sydney (SYD).**

## Overview
CommuteOps is a deterministic autonomous agent designed to solve the "recurring commute" problem. Unlike standard flight checkers, it calculates the **Total Cost of Commute** (Flight + Ground Transport + Parking) and optimizes for a rolling 3-month window. The main goal is to make life easier for myself by autonomously planning travel (optomised for lowest cost), but also to gain valuable insights on when is the 'best' time to book in advance.

It runs on a monthly cron schedule to capture the booking curve, logging data for future predictive analysis while alerting the user to "Buy Now" opportunities via multi-channel notifications.

## Key Features
* **Dual-Port Analysis:** Compares **Avalon (AVV)** vs **Tullamarine (MEL)**.
    * *Smart Logic:* Automatically adds parking costs to AVV fares while treating MEL as a "Drop-off/Lift" scenario to find the true lowest cost.
* **Matrix Scanning:** Scans a flexibility matrix (Mon/Tue departures vs Thu/Fri/Sat returns) rather than single dates.
* **Data Historian:** Logs all pricing data to CSV to build a dataset for analyzing booking curves and price velocity over time.
* **Surge Protection:** Benchmarks hotel rates to detect event-driven price surges in Sydney.
* **Actionable Alerts:**
    * **Email:** HTML report with Deep Links and attached `.ics` calendar files for one-click scheduling.
    * **Push:** Real-time notifications via Pushover for immediate deal awareness.

## Tech Stack
* **Python 3.10+**
* **SerpApi** (Real-time Google Flights/Hotels Engine)
* **ICS** (iCal generation)
* **Pushover** (Mobile Notifications)
* **SMTP** (Email Reporting)

## Usage
Designed to run as a monthly CRON job:
`0 9 1 * * /usr/bin/python3 commute-ops.py`
