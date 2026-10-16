// The header comments of custom event code ("; NAME: ...", "// GAMES: MP1_USA,MP3_USA",
// "// EXECUTION: Direct", "// PARAM: Number|count"), kept in step with the event form as the
// original's create-event views did (customevents.ts CustomAsmHelper, createevent_*.tsx).
// The server reads the same comments when it saves the event.

/** The games, in the original's order: [name, id, label]. */
export const GAMES = [
  ['MP1_USA', 'CLBE', 'MP1 USA'], ['MP2_USA', 'NMWE', 'MP2 USA'], ['MP3_USA', 'NMVE', 'MP3 USA'],
  ['MP1_JPN', 'CLBJ', 'MP1 JPN'], ['MP2_JPN', 'NMWJ', 'MP2 JPN'], ['MP3_JPN', 'NMVJ', 'MP3 JPN'],
  ['MP1_PAL', 'NLBP', 'MP1 PAL'], ['MP2_PAL', 'NMWP', 'MP2 PAL'], ['MP3_PAL', 'NMVP', 'MP3 PAL'],
];
export const GAME_BY_ID = Object.fromEntries(GAMES.map(g => [g[1], g]));
export const GAME_BY_NAME = Object.fromEntries(GAMES.map(g => [g[0], g]));

/** Parameter types (EventParameterType), with their labels. */
export const PARAM_TYPES = [
  ['Boolean', 'Boolean'], ['Number', 'Number'], ['+Number', 'Positive Number'],
  ['Space', 'Space'], ['Space[]', 'Space Array'],
];
export const VALID_PARAM_NAME = /^[\w?!]*$/;

const EXEC_NAMES = { 1: 'Direct', 2: 'Process' };

const propRegex = (prop, flags = 'im') => new RegExp(`^\\s*[;\\/]+\\s*${prop}:(.+)$`, flags);

export function readProperty(code, prop) {
  const m = propRegex(prop).exec(code);
  return m ? m[1] : null;
}

export function readPropertySet(code, prop) {
  return [...code.matchAll(propRegex(prop, 'gim'))].map(m => m[1].trim());
}

/** The form's values read from the code: {name, games (ids), executionType, parameters}. */
export function readHeader(code) {
  const name = readProperty(code, 'NAME');
  const gamesValue = readProperty(code, 'GAMES');
  const games = gamesValue === null ? null
    : gamesValue.trim().split(',').map(s => GAME_BY_NAME[s.trim()]?.[1]).filter(Boolean);
  const execValue = readProperty(code, 'EXECUTION');
  const exec = execValue ? ({ Direct: 1, Process: 2 }[execValue.trim()] ?? null) : null;
  const parameters = [];
  for (const entry of readPropertySet(code, 'PARAM')) {
    const pieces = entry.split('|');
    if (pieces.length !== 2) continue;
    const [type, pname] = pieces;
    if (!PARAM_TYPES.some(t => t[0] === type) || !pname || !VALID_PARAM_NAME.test(pname)) continue;
    if (parameters.some(p => p.name === pname)) continue;
    parameters.push({ name: pname, type });
  }
  return { name: name === null ? null : name.trim(), games, executionType: exec, parameters };
}

function clearProperties(code, props) {
  for (const p of props) {
    code = code.replace(new RegExp(`^\\s*[;\\/]+\\s*${p}:.*[\\r\\n]*`, 'gim'), '');
  }
  return code;
}

/**
 * The code with its header rewritten from the form's values (syncTextToStateVars).
 * @param {string} code
 * @param {{name: string, games: !Array<string>, executionType: number, parameters: !Array}} form
 * @param {number} language 0 MIPS (";" comments), 1 C ("//").
 */
export function writeHeader(code, form, language) {
  const cc = language === 1 ? '//' : ';';
  let out = '\n' + clearProperties(code, ['NAME', 'GAMES', 'EXECUTION', 'PARAM']);
  for (let i = form.parameters.length - 1; i >= 0; i--) {
    out = `${cc} PARAM: ${form.parameters[i].type}|${form.parameters[i].name}\n` + out;
  }
  out = `${cc} EXECUTION: ${EXEC_NAMES[form.executionType] || 'Direct'}\n` + out;
  out = `${cc} GAMES: ${form.games.map(id => GAME_BY_ID[id]?.[0]).filter(Boolean).join(',')}\n` + out;
  out = `${cc} NAME: ${form.name.trim()}\n` + out;
  return out;
}

export const DEFAULT_CODE = {
  1: `// NAME:
// GAMES:
// EXECUTION: Direct

#include "ultra64.h"

void main() {
    // Your code here!
    // For code examples, see:
    // https://github.com/PartyPlanner64/events
}`,
  0: `; NAME:
; GAMES:
; EXECUTION: Direct

ADDIU SP SP -4
SW RA 0(SP)

; Your code here
; For code examples, see:
; https://github.com/PartyPlanner64/events

LW RA 0(SP)
JR RA
ADDIU SP SP 4`,
};
