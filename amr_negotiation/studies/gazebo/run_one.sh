#!/bin/sh
# args: seed policy rulebook label slot
s=$1; p=$2; rb=$3; lab=$4
mkdir -p ${GZSWEEP:-$HOME/studies/gzsweep}/out/$lab
dom=$(( (s * 7 + $(echo $lab | cksum | cut -c1-3)) % 200 + 10 ))
RB=""; [ "$rb" != "-" ] && RB="rulebook:=$rb"
docker run --rm -e ROS_DOMAIN_ID=$dom -e GZ_PARTITION=gz$dom -v ${GZSWEEP:-$HOME/studies/gzsweep}/scen:/scen -v ${GZSWEEP:-$HOME/studies/gzsweep}/out/$lab:/results amrneg \
  ros2 launch amr_negotiation_ros corridor.launch.py scenario:=/scen/gz_s$s.yaml policy:=$p $RB seed:=$s record:=false > ${GZSWEEP:-$HOME/studies/gzsweep}/out/$lab/log_s$s.txt 2>&1
echo "done $s $lab $(ls ${GZSWEEP:-$HOME/studies/gzsweep}/out/$lab/*s$s*.json 2>/dev/null | wc -l)"
