#!/bin/bash
# Menjalankan Chrome untuk 5 akun Threads dengan flag hemat RAM
# --disable-gpu --disable-software-rasterizer (test sukses di avelinefinds 9228)
declare -A PROFILES=(
  [9222]=/home/ubuntu/chrome-profile-bot
  [9223]=/home/ubuntu/chrome-profile-lanadealsrey2
  [9226]=/home/ubuntu/chrome-profile-renaisher
  [9227]=/home/ubuntu/chrome-profile-kailaaak7
  [9228]=/home/ubuntu/chrome-profile-avelinefinds
)
for port in "${!PROFILES[@]}"; do
  google-chrome --remote-debugging-port=$port --user-data-dir=${PROFILES[$port]} \
    --no-first-run --no-default-browser-check --remote-allow-origins=* --headless=new \
    --noerrdialogs --ozone-platform=headless --disable-dev-shm-usage --window-size=1280,900 \
    --renderer-process-limit=2 --process-per-site --js-flags=--max-old-space-size=96 \
    --disable-features=BackForwardCache,MediaRouter,Translate,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion \
    --disk-cache-size=10485760 --disable-background-networking --metrics-recording-only \
    --disable-component-update --disable-domain-reliability --no-pings --num-raster-threads=1 \
    --ozone-override-screen-size=800,600 --use-angle=swiftshader-webgl \
    --disable-gpu --disable-software-rasterizer \
    >> /dev/null 2>&1 &
  echo "Launch Chrome port $port (PID $!)"
done
wait 2>/dev/null
