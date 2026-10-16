// Shows a space's AI decision tree (port of aieditor.tsx), read-only, in a dialog.
import { dialog, esc } from '../api.js';
import { hexstr } from './board.js';

const T = {
  leaf: 0, hasCoins: 1, star: 2, remainingSpaces: 3, stateComparison: 4, winningHeuristic: 5,
  customCode: 6, turnsElapsed: 7, hasItem: 8,
};

function condition(node) {
  switch (node.type) {
    case T.leaf: return '';
    case T.hasCoins: return `Has ${esc(node.data)} coins`;
    case T.star: return `Stars: ${hexstr(node.data)}`;
    case T.remainingSpaces: return `Player has ${esc(node.data)} remaining spaces`;
    case T.stateComparison: return `State ${hexstr(node.data)}`;
    case T.winningHeuristic: return `Heuristic ${hexstr(node.data)}`;
    case T.customCode: return `Custom function at ${hexstr(node.data)}`;
    case T.turnsElapsed: return `${esc(node.data)} turns elapsed`;
    case T.hasItem: return `Has the ${hexstr(node.data)} item`;
  }
  return 'Unknown Condition!';
}

function difficulty(short, long, p) {
  return `<span class="ai-diff" title="Probability on ${long} difficulty">${short}: <b>${esc(p)}</b></span>`;
}

function result(node) {
  const r = node.decision;
  const p = r.probability || [];
  let html = `<span class="ai-decision" title="The space index the computer player heads to">${esc(r.value)}</span> @ `;
  html += difficulty('E', 'Easy', p[0]) + ' ';
  html += p.length === 2 ? difficulty('N/H', 'Normal / Hard', p[1]) : difficulty('N', 'Normal', p[1]);
  if (p.length > 2) html += ' ' + difficulty('H', 'Hard', p[2]) + ' ' + difficulty('SH', 'Super Hard', p[3]);
  return `<div class="ai-result">${html}</div>`;
}

function nodeHtml(node) {
  const cond = condition(node);
  const children = Array.isArray(node.decision) ? node.decision.map(nodeHtml).join('') : result(node);
  return `<div class="ai-node">${cond ? `<div class="ai-cond">${cond}</div>` : ''}${children}</div>`;
}

export function showDecisionTree(tree, spaceIndex) {
  const body = tree && tree.length
    ? `<p class="hint">How computer players choose a path at space ${spaceIndex}: conditions are checked in order, and the first that holds picks the next space, with a probability per difficulty.</p><div class="ai-tree">${tree.map(nodeHtml).join('')}</div>`
    : '<p>No decision tree provided.</p>';
  return dialog({ title: 'AI Decision Tree', body, wide: true });
}
