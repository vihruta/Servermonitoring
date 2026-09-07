#!/bin/bash

if ! command -v smartctl >/dev/null 2>&1; then
    echo "Installing smartmontools..."
    sudo apt update
    sudo apt install -y smartmontools
else
    echo "smartctl already installed"
fi