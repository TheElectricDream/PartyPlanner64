// NAME:   Main Entry   
// GAMES: MP2_USA, MP3_USA
// EXECUTION: Process
//PARAM: Boolean|enabled
// param: Number|lower_case_prop
// PARAM: Number|bad name
// PARAM: Number|bad|pipes
// PARAM: Bogus|bogus_type
// PARAM: Number|ok_name?!
helper:
  jr RA
  nop
main:
  addiu SP, SP, -0x18
  sw RA, 0x10(SP)
  jal helper
  nop
  lw RA, 0x10(SP)
  jr RA
  addiu SP, SP, 0x18
