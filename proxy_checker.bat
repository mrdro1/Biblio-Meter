python proxy_checker.py -i proxies.txt -o tmp_proxies -r 3 -t 2000 -k 3 -p 50
python proxy_checker.py -i tmp_proxies -o proxies_good.txt -r 3 -t 2000 -k 3 -p 50 -g