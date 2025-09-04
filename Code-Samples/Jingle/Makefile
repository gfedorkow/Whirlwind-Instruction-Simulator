
PGM=jingle

TAPE=102766748_100-6-900_jingle_bells.7ch

TCORE=jingle_gs001_FB100-6-900.tcore

${PGM}.lst: ${PGM}.ww Makefile 
	wwasm ${PGM}.ww  -o ${PGM}

${PGM}.tcore: Makefile ${TAPE}
	 wwutd ${TAPE} -o ${PGM}

${PGM}.ww: ${PGM}.tcore Makefile 
	wwdisasm ${TCORE} -z -o ${PGM}.ww
