#!/bin/bash
mkdir -p public
echo '' > public/placeholder.html

if command -v g++ >/dev/null; then
  echo "g++ is installed, attempting to compile the chess engine..."
  if g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main; then
    chmod +x game/engine/main
    echo "Chess engine compiled successfully."
  else
    echo "g++ compilation failed, using Python engine fallback"
  fi
else
  echo "No g++ compiler found, using Python engine"
fi
