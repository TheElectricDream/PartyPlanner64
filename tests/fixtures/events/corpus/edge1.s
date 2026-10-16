; NAME: Edge Case One
; GAMES: MP1_USA,MP2_USA,MP3_USA
; EXECUTION: Direct
; PARAM: Number|coins
; PARAM: Boolean|flag
; PARAM: Space|target
; PARAM: +Number|amount
; PARAM: Space[]|targets
; PARAM: Number[]|numbers
ADDIU SP SP -0x18
SW RA 0x10(SP)
loop: label2: nop
foo:
foobar:
  j foo
  j foobar ; foo foobar foo_bar
  lui A0, hi(D_800CD0AA)
  lw A0, lo(D_800CD0AA)(A0)
  jal func_8004A520
  jal func_8004a520
  jal func_8004A520
  jal func_80012345
func_80012345:
  nop
D_80011111:
  .word D_80011111, D_80022222
  .word D_80022222
@already_scoped:
  @@local:
  nop ; b @@local
.definelabel MYCONST,5
.definelabel  SPACED_CONST , 6
MY_EQU equ 7
OTHER_EQU   EQU   8
notequ:
  equ_thing: nop
.definelabel __PP64_INTERNAL_THING,1
weird?label!: nop
  addiu A0, R0, MYCONST
  addiu A1, R0, MY_EQU
.beginstatic
static_helper:
  jr RA
  nop
static_data:
  .word static_helper
.endstatic
  jal static_helper
  LW RA 0x10(SP)
  JR RA
  ADDIU SP SP 0x18
