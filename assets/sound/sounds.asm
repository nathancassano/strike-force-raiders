;this file generated with SNES GSS tool

.define SFX_PLAYER_GUN1	0
.define SFX_PLAYER_GUN2	1
.define SFX_PLAYER_GUN3	2
.define SFX_PLAYER_GUN4	3
.define SFX_GROUND_HIT	4
.define SFX_PLAYER_HIT	5
.define SFX_ENEMY_HIT	6
.define SFX_PLAYER_MISSILE	7
.define SFX_PLAYER_FLARE	8
.define SFX_ENEMY_GUN	9
.define SFX_ENEMY_CANNON	10
.define SFX_ENEMY_MISSILE	11
.define SFX_EXPLODE_1	12
.define SFX_EXPLODE_2	13
.define SFX_PRINTER_TYPE	14
.define SFX_PRINTER_ROLL	15
.define SFX_HELI_1	16
.define SFX_HELI_2	17
.define SFX_HELI_3	18
.define SFX_HELI_4	19
.define SFX_HELI_TAKE_OFF	20
.define SFX_HELI_LANDING	21
.define SFX_NO_MISSILE	22
.define SFX_MISSILE_WARNING	23
.define SFX_MESSAGE	24
.define SFX_MENU_MOVE	25
.define SFX_MENU_SELECT	26
.define SFX_MENU_START	27
.define SFX_MENU_WRONG_PASSWORD	28

.define MUS_OPERATION_HINDSTRIKE	0
.define MUS_YOU_HAVE_YOUR_ORDERS	1
.define MUS_FIRE_FROM_THE_SKY	2
.define MUS_FIRST_ROUND_IS_ON_ME	3
.define MUS_BLOWED_UP_SIR_	4
.define MUS_CONGRATULATIONS	5
.define MUS_CONTROLS	6

.section ".roDataSoundCode1" superfree
spc700_code_1:	.incbin "spc700.bin" skip 0 read 32768
.ends

.section ".roDataSoundCode2" superfree
spc700_code_2:	.incbin "spc700.bin" skip 32768
.ends

.section ".roDataMusic1" superfree
music_1_data:	.incbin "music_1.bin"
.ends

.section ".roDataMusic2" superfree
music_2_data:	.incbin "music_2.bin"
.ends

.section ".roDataMusic3" superfree
music_3_data:	.incbin "music_3.bin"
.ends

.section ".roDataMusic4" superfree
music_4_data:	.incbin "music_4.bin"
.ends

.section ".roDataMusic5" superfree
music_5_data:	.incbin "music_5.bin"
.ends

.section ".roDataMusic6" superfree
music_6_data:	.incbin "music_6.bin"
.ends

.section ".roDataMusic7" superfree
music_7_data:	.incbin "music_7.bin"
.ends

