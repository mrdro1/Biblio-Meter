python proxy_finder.py -q 163.121.187.181:8080 -c 1 -o proxies.txt
python proxy_checker.py -i proxies.txt -o tmp_proxies -r 3 -t 5000 -k 3 -p 50
python proxy_checker.py -i tmp_proxies -o proxies_good.txt -g -t 3000 -k 3 -p 50