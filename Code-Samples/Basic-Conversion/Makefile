

SRC=src-to-assemble
#TCORE=102782043_3600m0_basic_conversion_5-13-54_copy_gs001.tcore 
TCORE=bc-merged.tcore 
ASM=bc

${ASM}.svg: ${ASM}.flow.gv
	dot -Tsvg ${ASM}.flow.gv -o ${ASM}.flow.svg

${ASM}.flow.gv: ${ASM}.acore ${SRC}.petrB
	wwsim ${ASM}.acore -fo ${ASM}.flow.gv --PETRB src-to-assemble.petrB --DumpCore ${ASM}.dcore

# make the source-file "tape" in CS format to drive the assembler
src-to-assemble.petrB: ${SRC}.cs
	ww-ASCII-to-Flexo -i ${SRC}.cs -o ${SRC}.petrB

${ASM}.ww: ${TCORE}
	wwdisasm --out ${ASM}.ww ${TCORE} --NoComment


${ASM}.acore: ${ASM}.ww
	wwasm ${ASM}.ww

