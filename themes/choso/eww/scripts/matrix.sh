#!/bin/bash
# Matrix-like generator for Eww
ROWS=48
COLS=1
CHARS="010101$#%&"

for ((i=0; i<ROWS; i++)); do
    line=""
    for ((j=0; j<COLS; j++)); do
        # 30% chance to show a character, else space
        if (( RANDOM % 10 < 3 )); then
            line+="${CHARS:RANDOM%${#CHARS}:1} "
        else
            line+="  "
        fi
    done
    echo "$line"
done
