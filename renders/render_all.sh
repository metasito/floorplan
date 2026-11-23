#!/bin/zsh
# Render every style from every view. Usage: render_all.sh <out_dir> <samples> <width> <height> [extra args]
out=$1; samples=$2; w=$3; h=$4; shift 4
here=${0:A:h}
mkdir -p "$out"
for style in modern minimal scandinavian industrial midcentury boho traditional; do
  for view in lounge dining; do
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --disable-autoexec \
      --python "$here/render_interiors.py" -- --style $style --view $view --samples $samples \
      --res $w $h --out "$out/${style}_${view}.png" "$@" 2>&1 | grep -E "Traceback|Error:|rendered"
  done
done
