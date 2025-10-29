# UNITN Courses Explorer

# ALERT

Before using this script, look for CINECA content policy. This script is only intended for learning/didactic purposes. 

# Instructions

When choosing courses, it's a bit difficult to get all the info you need. This script allows you to do that. 

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

To have the starting `data.json` file, go to https://unitn.coursecatalogue.cineca.it/cerca-insegnamenti , insert the filters of the course you want, then do 'EXPORT XSLX' after doing 'SUBMIT'. (the website in this case is in english). 

Convert the XSLS in JSON, via a tool online. Then you have data.json. 

```bash
python3 script.py
```

In the file `specific.txt`, write the exact names of the courses your interested in. If the file is empty, all the courses in data.json will be scraped. 

Data will be gathered in `unitn_data_specific`, and then at the end a file will be created with all scraped data: a JSON and CSV file will be created. 


