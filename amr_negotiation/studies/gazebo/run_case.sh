#!/bin/sh
# args: index seed label scenario policy_file [group]; $GZSWEEP holds scen/ (with scen/pol/) and out/<label>/.
# The index sets ROS_DOMAIN_ID / GZ_PARTITION, so runs started together never share a domain.
i=$1; s=$2; lab=$3; scn=$4; pf=$5
D=${GZSWEEP:-$HOME/studies/gzall}
mkdir -p $D/out/$lab
dom=$(( i % 200 + 10 ))
p=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['name'])" $D/scen/pol/$pf)
docker run --rm -e ROS_DOMAIN_ID=$dom -e GZ_PARTITION=gz$dom -v $D/scen:/scen -v $D/out/$lab:/results ${AMRNEG_IMAGE:-amrneg} \
  ros2 launch amr_negotiation_ros corridor.launch.py scenario:=/scen/$scn.yaml policy:=$p policy_file:=/scen/pol/$pf \
  seed:=$s record:=false > $D/out/$lab/log_$scn.txt 2>&1
echo "done $scn $lab $(ls $D/out/$lab/${scn}_*.json 2>/dev/null | wc -l)"
