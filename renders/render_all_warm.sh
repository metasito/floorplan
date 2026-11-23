#!/bin/zsh
# Final renders of the warm scheme. Usage: render_all_warm.sh [out_dir]
# Each line is one Blender process: views in a process share one build and one light mood.
here=${0:A:h}
out=${1:-$here/out_warm/raw}
mkdir -p "$out"
B=/Applications/Blender.app/Contents/MacOS/Blender
log=$out/render.log
run() {
  echo "=== $(date '+%H:%M:%S') $*" | tee -a "$log"
  $B -b --factory-startup --disable-autoexec --python "$here/shoot.py" -- --out "$out" "$@" 2>&1 \
    | grep -E --line-buffered "Traceback|Error|rendered|skipped" | tee -a "$log"
}
STILL=(--samples 768 --noise 0.008 --res 3000 2000)
PANO=(--pano-samples 512 --noise 0.012 --pano-res 4096 2048)

run --views living_day kitchen_day hall bedroom1 bedroom2 bath1 bath2 $STILL
run --views living_dusk $STILL
run --views balcony_a balcony_b $STILL
run --views cutaway topplan $STILL
run --views pano_living pano_dining pano_hall pano_bedroom1 pano_bedroom2 pano_bath1 pano_bath2 $PANO
run --views pano_balcony $PANO
echo "=== $(date '+%H:%M:%S') all done" | tee -a "$log"
