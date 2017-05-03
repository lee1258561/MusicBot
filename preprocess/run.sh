#!/bin/bash

TEMPLATES=("search.csv" "recommend.csv" "info.csv" "neutral.csv")
DATA_DIR="../data/"
TEMPLATE_DIR="../data/template/"
OUT_PATH="../data/nlu_data/"
NB_PER_TEMP=1000

mkdir $OUT_PATH
if [ $? -ne 0 ];then
	echo "Please make sure there's no Train* files in $OUT_PATH!"
	sleep 5
	echo "continue..."
fi

echo "make dataset ..."
for i in ${TEMPLATES[@]}
do
	python2 sentence_generate.py ${TEMPLATE_DIR}$i ${DATA_DIR}/chinese_artist.json ${DATA_DIR}/genres.json\
		--nb_per_template $NB_PER_TEMP\
		-o $OUT_PATH/Train
done

echo "make train, valid, test sets..."
python2 split_data.py $OUT_PATH -o $OUT_PATH
