//this file generated with SNES GSS tool

#define SOUND_EFFECTS_ALL	29

#define MUSIC_ALL	7

//sound effect aliases

enum {
	SFX_PLAYER_GUN1=0,
	SFX_PLAYER_GUN2=1,
	SFX_PLAYER_GUN3=2,
	SFX_PLAYER_GUN4=3,
	SFX_GROUND_HIT=4,
	SFX_PLAYER_HIT=5,
	SFX_ENEMY_HIT=6,
	SFX_PLAYER_MISSILE=7,
	SFX_PLAYER_FLARE=8,
	SFX_ENEMY_GUN=9,
	SFX_ENEMY_CANNON=10,
	SFX_ENEMY_MISSILE=11,
	SFX_EXPLODE_1=12,
	SFX_EXPLODE_2=13,
	SFX_PRINTER_TYPE=14,
	SFX_PRINTER_ROLL=15,
	SFX_HELI_1=16,
	SFX_HELI_2=17,
	SFX_HELI_3=18,
	SFX_HELI_4=19,
	SFX_HELI_TAKE_OFF=20,
	SFX_HELI_LANDING=21,
	SFX_NO_MISSILE=22,
	SFX_MISSILE_WARNING=23,
	SFX_MESSAGE=24,
	SFX_MENU_MOVE=25,
	SFX_MENU_SELECT=26,
	SFX_MENU_START=27,
	SFX_MENU_WRONG_PASSWORD=28
};

//sound effect names

const char* const soundEffectsNames[SOUND_EFFECTS_ALL]={
	"PLAYER_GUN1",	//0
	"PLAYER_GUN2",	//1
	"PLAYER_GUN3",	//2
	"PLAYER_GUN4",	//3
	"GROUND_HIT",	//4
	"PLAYER_HIT",	//5
	"ENEMY_HIT",	//6
	"PLAYER_MISSILE",	//7
	"PLAYER_FLARE",	//8
	"ENEMY_GUN",	//9
	"ENEMY_CANNON",	//10
	"ENEMY_MISSILE",	//11
	"EXPLODE 1",	//12
	"EXPLODE 2",	//13
	"PRINTER_TYPE",	//14
	"PRINTER_ROLL",	//15
	"HELI_1",	//16
	"HELI_2",	//17
	"HELI_3",	//18
	"HELI_4",	//19
	"HELI_TAKE_OFF",	//20
	"HELI_LANDING",	//21
	"NO_MISSILE",	//22
	"MISSILE_WARNING",	//23
	"MESSAGE",	//24
	"MENU_MOVE",	//25
	"MENU_SELECT",	//26
	"MENU_START",	//27
	"MENU_WRONG_PASSWORD"	//28
};

//music effect aliases

enum {
	MUS_OPERATION_HINDSTRIKE=0,
	MUS_YOU_HAVE_YOUR_ORDERS=1,
	MUS_FIRE_FROM_THE_SKY=2,
	MUS_FIRST_ROUND_IS_ON_ME=3,
	MUS_BLOWED_UP_SIR_=4,
	MUS_CONGRATULATIONS=5,
	MUS_CONTROLS=6
};

//music names

const char* const musicNames[MUSIC_ALL]={
	"OPERATION HINDSTRIKE",	//0
	"YOU HAVE YOUR ORDERS",	//1
	"FIRE FROM THE SKY",	//2
	"FIRST ROUND IS ON ME",	//3
	"BLOWED UP,SIR!",	//4
	"CONGRATULATIONS",	//5
	"CONTROLS"	//6
};

extern const unsigned char spc700_code_1[];
extern const unsigned char spc700_code_2[];
extern const unsigned char music_1_data[];
extern const unsigned char music_2_data[];
extern const unsigned char music_3_data[];
extern const unsigned char music_4_data[];
extern const unsigned char music_5_data[];
extern const unsigned char music_6_data[];
extern const unsigned char music_7_data[];

const unsigned char* const musicData[MUSIC_ALL]={
	music_1_data,
	music_2_data,
	music_3_data,
	music_4_data,
	music_5_data,
	music_6_data,
	music_7_data
};
