from joblib import Parallel, delayed
import multiprocessing
import os
import random
import time
import json

def processInput(query):
    time.sleep(random.random())
    bat_template = json.loads(open("getPapersByKeyWords.ctl").read())
    with open(f"""temp/{query}.ctl""", "w") as f:
        bat_template["query"] = query
        f.write(json.dumps(bat_template))
    os.system(f"""python bibliometer.py -l logbook.log -d papers.db3 -c "temp/{query}.ctl" -p proxies.txt""")

 
num_cores = 20
results = Parallel(n_jobs=num_cores)(delayed(processInput)(q.strip()) for q in open("queries.txt"))