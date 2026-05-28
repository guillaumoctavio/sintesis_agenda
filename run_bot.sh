#!/bin/bash
source /home/oc/.env_sintesis
cd /home/oc/repositorios/sintesis_agenda
exec /usr/bin/python3 bot_listener.py
