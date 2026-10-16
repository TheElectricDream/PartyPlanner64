; NAME: Game Specific
; GAMES: MP1_USA,MP3_USA
; EXECUTION: Direct
; PARAM: Space|where
  jal GetBasicPromptSelection
  nop
  addiu A0, R0, where_chain_index
  jal ShowPlayerCoinChange
  nop
