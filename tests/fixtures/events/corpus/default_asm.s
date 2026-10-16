; NAME: Default Asm
; GAMES: MP1_USA,MP2_USA,MP3_USA
; EXECUTION: Direct

ADDIU SP SP -4
SW RA 0(SP)

; Your code here
; For code examples, see:
; https://github.com/PartyPlanner64/events

LW RA 0(SP)
JR RA
ADDIU SP SP 4