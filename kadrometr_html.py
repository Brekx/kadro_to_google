from datetime import date, datetime, time
import json
with open("savings.json", 'r') as inputfile:
  try:
    base = json.load(inputfile)
  except:
    base = {}

def reAuthorization(http):
  http.headers['Authorization'] = ""
  r = http.request('POST', 'https://api.kadromierz.pl/security/authentication', body=json.dumps(
      {'email': base['credentials']['email'], 'password': base['credentials']['password']}))
  base['credentials']['authToken'] = json.loads(
      r.data.decode('utf8').replace("'", '"'))['auth_token']
  with open("savings.json", 'w') as outputfile:
    outputfile.write(json.dumps(base))
  print("Renewed auth token")

def getActualSchedule(dtstart: datetime, dtend: datetime):
  import urllib3
  from datetime import datetime
  http = urllib3.PoolManager()
  has_key = True
  try:
    base['credentials']['authToken']
  except Exception as e:
    has_key = False
  if not has_key or base['credentials']['authToken'] == "":
    reAuthorization(http)
  http.headers['Authorization'] = 'AUTH-TOKEN token="' + \
    base['credentials']['authToken'] + '"'
  start = dtstart.strftime("%Y-%m-%d")
  end = dtend.strftime("%Y-%m-%d")
  ret = []
  locations = []
  r = http.request('GET', 'https://api.kadromierz.pl/users/current/locations')
  if(r.status!=200):
    reAuthorization(http)
    http.headers['Authorization'] = 'AUTH-TOKEN token="' + \
      base['credentials']['authToken'] + '"'
    r = http.request('GET', 'https://api.kadromierz.pl/users/current/locations')
    
  data = json.loads(r.data.decode('utf8').replace("'", '"'))
  
  for att in data['locations']:
    locations.append(att['id'])
  for loc in locations:
    r = http.request('GET', 'https://api.kadromierz.pl/locations/' + loc + '/schedule?from=' + start + '&to=' + end + '&show_drafts=false')
    data = json.loads(r.data.decode('utf8').replace("'", '"'))
    if not "schedule" in data:
      raise Exception("Wrong credentials")
    for k in data['schedule']['employees']:
      if not k in ret:
        ret.append(k)

  if r.status != 200 and r.status != 404:
    base['credentials']['authToken'] = ""
    raise Exception("No kadrometr authorization")
  return ret

def getWeekCalendar(start: datetime, end: datetime) -> dict:
  from datetime import datetime, timedelta

  schedule_data = getActualSchedule(start, end)
  schedule = {}
  for employee in schedule_data:
    employee_shifts = []
    for shift in employee['shifts_for_other_locations']:
      start = datetime(int(shift['start_timestamp'][0:4]), int(shift['start_timestamp'][5:7]), int(shift['start_timestamp'][8:10]), int(shift['start_timestamp'][11:13]), int(shift['start_timestamp'][14:16]), int(shift['start_timestamp'][17:19]))
      end = datetime(int(shift['end_timestamp'][0:4]), int(shift['end_timestamp'][5:7]), int(shift['end_timestamp'][8:10]), int(shift['end_timestamp'][11:13]), int(shift['end_timestamp'][14:16]), int(shift['end_timestamp'][17:19]))
      new_event = {'dtstart' : start, 'dtend' : end, 'location' : shift['job_title']['title'], 'note' : ""}
      employee_shifts.append(new_event)
    for shift in employee['shifts']:
      start = datetime(int(shift['start_timestamp'][0:4]), int(shift['start_timestamp'][5:7]), int(shift['start_timestamp'][8:10]), int(shift['start_timestamp'][11:13]), int(shift['start_timestamp'][14:16]), int(shift['start_timestamp'][17:19]))
      end = datetime(int(shift['end_timestamp'][0:4]), int(shift['end_timestamp'][5:7]), int(shift['end_timestamp'][8:10]), int(shift['end_timestamp'][11:13]), int(shift['end_timestamp'][14:16]), int(shift['end_timestamp'][17:19]))
      new_event = {'dtstart' : start, 'dtend' : end, 'location' : shift['job_title']['title'], 'note' : ""}
      employee_shifts.append(new_event)
    employee_record = {'name' : employee['first_name'] + ' ' + employee['last_name'], \
                        'schedule' : employee_shifts}
    schedule[employee['id']] = employee_record

  employees_to_fill = list(schedule.keys())
  for employee in range(0, len(schedule)-1): 
    employee_id = employees_to_fill.pop(0)
    for shift in schedule[employee_id]['schedule']:
      for other_employer_id in employees_to_fill:
        for other_employer_shift in schedule[other_employer_id]['schedule']:
          if( shift['location'] == other_employer_shift['location'] and
              (( shift['dtstart'] >= other_employer_shift['dtstart'] and shift['dtstart'] < other_employer_shift['dtend']) or
               ( shift['dtstart'] <= other_employer_shift['dtstart'] and shift['dtend'] > other_employer_shift['dtstart']))):
            note = schedule[other_employer_id]['name']
            earlier = shift['dtstart'] < other_employer_shift['dtstart']
            later = shift['dtend'] > other_employer_shift['dtend']
            if(earlier and not later):
              note += ' (od ' + other_employer_shift['dtstart'].strftime("%H:%M") + ')'
            if(earlier and later):
              note += ' (od ' + other_employer_shift['dtstart'].strftime("%H:%M") + ' do ' + other_employer_shift['dtend'].strftime("%H:%M") + ')'
            if(not earlier and later):
              note += ' (do ' + other_employer_shift['dtend'].strftime("%H:%M") + ')'
            shift['note'] += note if shift['note'] == "" else ('\n' + note)
            note = schedule[employee_id]['name']
            earlier = other_employer_shift['dtstart'] < shift['dtstart']
            later = other_employer_shift['dtend'] > shift['dtend']
            if(earlier and not later):
              note += ' (od ' + shift['dtstart'].strftime("%H:%M") + ')'
            if(earlier and later):
              note += ' (od ' + shift['dtstart'].strftime("%H:%M") + ' do ' + shift['dtend'].strftime("%H:%M") + ')'
            if(not earlier and later):
              note += ' (do ' + shift['dtend'].strftime("%H:%M") + ')'
            other_employer_shift['note'] += note if other_employer_shift['note'] == "" else ('\n' + note)

  return schedule

def getShifts(start: datetime, end: datetime) -> dict:
  from datetime import datetime, timedelta
  ret = {}
  while start != end:
    tend = end
    if start.month != tend.month:
      tend = (datetime(start.year, start.month + 1, 1, 0, 1) if start.month+1<13 else datetime(start.year + 1, 1, 1, 0, 1)) - timedelta(1)
      for calId, cal in getWeekCalendar(start, tend).items():
        if calId in ret:
          ret[calId]['schedule'] += cal['schedule']
        else:
          ret[calId] = cal
      start = tend + timedelta(1)
    else:
      for calId, cal in getWeekCalendar(start, end).items():
        if calId in ret:
          ret[calId]['schedule'] += cal['schedule']
        else:
          ret[calId] = cal
      start = end
  return ret