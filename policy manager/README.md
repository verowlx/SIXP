# Policy Manager
Web graphical interface to configure SNMP bandwidth polling, call `monitor_interface_bandwidth`, and store results in a NoSQL database.

## Features
- Configure SNMP target and polling options from browser
- Start/stop polling loop from UI
- Poll interface usage using `trafficmonitor/snmp_monitor.py`
- Store measurements in TinyDB (`policy_manager_db.json`)
- Show recent samples in a table

## Run
1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start app:
   - `python app.py`
3. Open:
   - `http://127.0.0.1:5000`

## Notes
- `Poll Interval` controls how often a new sample cycle starts.
- `Sample Window` is the window used inside `monitor_interface_bandwidth`.
- If `Poll Interval` is less than `Sample Window`, polling runs back-to-back.
