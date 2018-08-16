#!/bin/bash
python proxy_checker.py -i all_proxies.txt -o tmp_proxies -r 2 -t 2000 -k 1 -p 90
python proxy_checker.py -i tmp_proxies -o proxies.txt -r 3 -t 2000 -k 2 -p 90 -g
