#!/bin/bash

if ! command -v python3 &> /dev/null; then
  echo "Installing python3..."
  sudo apt update
  sudo apt install -y python3
fi

if ! command -v pip3 &> /dev/null; then
  echo "Installing pip3..."
  sudo apt update
  sudo apt install -y python3-pip
fi

if ! dpkg -l | grep -q python3-venv; then
  echo "Installing python3-venv..."
  sudo apt update
  sudo apt install -y python3-venv
fi

if ! dpkg -l | grep -q python3-tk; then
  echo "Installing python3-tk..."
  sudo apt update
  sudo apt install -y python3-tk
fi

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment .venv..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if [ -f "requirements.txt" ]; then
  echo "Running pip commands. This may take a while..."
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
fi

if [ -f "main.py" ]; then
  python main.py
fi

deactivate

