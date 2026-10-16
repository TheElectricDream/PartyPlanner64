// Draws each kind of space on a canvas (port of apps/partyplanner64/spaces.ts).
import { drawImg } from './images.js';

function circle(ctx, x, y, r, fill, stroke, lineWidth = 2) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, 2 * Math.PI);
  ctx.lineWidth = lineWidth;
  ctx.fillStyle = fill;
  ctx.strokeStyle = stroke;
  ctx.stroke();
  ctx.fill();
}

function image(ctx, name, x, y, half = 14) {
  ctx.save();
  drawImg(ctx, name, x - half, y - half);
  ctx.restore();
}

// Draws any star shape, helper method.
function drawStarShape(ctx, x, y, r, numPoints, radiusInsetFraction) {
  ctx.save();
  ctx.beginPath();
  ctx.translate(x, y);
  ctx.moveTo(0, 0 - r);
  for (let i = 0; i < numPoints; i++) {
    ctx.rotate(Math.PI / numPoints);
    ctx.lineTo(0, 0 - r * radiusInsetFraction);
    ctx.rotate(Math.PI / numPoints);
    ctx.lineTo(0, 0 - r);
  }
  ctx.fill();
  ctx.restore();
}

function drawOtherR(ctx, x, y, radius) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, 2 * Math.PI);
  ctx.lineWidth = radius / 6;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
  ctx.stroke();
  ctx.lineWidth = radius / 4;
  ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
  ctx.strokeStyle = 'black';
  ctx.setLineDash([radius / 2, 3]);
  ctx.stroke();
  ctx.fill();
  ctx.restore();
}

function drawStarSpace(ctx, x, y, radius) {
  ctx.save();
  // Transparent base circle
  circle(ctx, x, y, radius, 'rgba(0, 0, 0, 0.2)', 'rgba(0, 0, 0, 0.3)', radius / 8);
  // Add yellow star on top
  ctx.fillStyle = 'yellow';
  drawStarShape(ctx, x, y, radius + 1, 5, 0.45);
  ctx.restore();
}

function drawStartR(ctx, x, y, radius, color) {
  ctx.save();
  circle(ctx, x, y, radius, color, 'rgba(255, 255, 255, 0.5)', 1);
  // Write the word "START"
  ctx.fillStyle = 'white';
  ctx.strokeStyle = 'black';
  ctx.lineWidth = 2;
  ctx.font = 'bold 12px monospace';
  ctx.textAlign = 'center';
  ctx.strokeText('START', x, y + 12);
  ctx.fillText('START', x, y + 12);
  ctx.restore();
}

function glyph(ctx, text, x, y, color) {
  ctx.fillStyle = color;
  ctx.font = 'bold 19px monospace';
  ctx.fillText(text, x - 6, y + 6);
}

export const spaces = {
  drawUnknown(ctx, x, y) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, 2 * Math.PI);
    ctx.fillStyle = 'orange';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fill();
    ctx.restore();
  },
  drawOther: (ctx, x, y) => drawOtherR(ctx, x, y, 8),
  drawOther3: (ctx, x, y) => drawOtherR(ctx, x, y, 12),
  drawBlue(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#0039ff', '#001281');
    ctx.restore();
  },
  drawBlue3: (ctx, x, y) => image(ctx, 'spaceBlue3', x, y),
  drawRed(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#ff3131', '#611515');
    ctx.restore();
  },
  drawRed3: (ctx, x, y) => image(ctx, 'spaceRed3', x, y),
  drawMiniGame(ctx, x, y) {
    // Same as blue
    ctx.save();
    circle(ctx, x, y, 8, '#0039ff', '#001281');
    // Add star on top.
    ctx.fillStyle = '#A4FFFF';
    drawStarShape(ctx, x, y, 8, 5, 0.45);
    ctx.restore();
  },
  drawMiniGameDuel3: (ctx, x, y) => image(ctx, 'spaceMiniGameDuel3', x, y),
  drawHappening(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#099f0a', '#2e681e');
    // Add ? on top
    glyph(ctx, '?', x, y, 'white');
    ctx.restore();
  },
  drawHappening3: (ctx, x, y) => image(ctx, 'spaceHappening3', x, y),
  drawHappeningDuel3: (ctx, x, y) => image(ctx, 'spaceHappeningDuel3', x, y),
  drawStar: (ctx, x, y) => drawStarSpace(ctx, x, y, 8),
  drawStar3: (ctx, x, y) => drawStarSpace(ctx, x, y, 12),
  drawChance(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#0039ff', '#001281');
    // Add '!'
    glyph(ctx, '!', x, y, '#ff3131');
    ctx.restore();
  },
  drawChance2(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#099f0a', '#2e681e');
    glyph(ctx, '!', x, y, 'white');
    ctx.restore();
  },
  drawChance3: (ctx, x, y) => image(ctx, 'spaceChance3', x, y),
  drawStart: (ctx, x, y) => drawStartR(ctx, x, y, 8, 'black'),
  drawStart3: (ctx, x, y) => drawStartR(ctx, x, y, 12, 'black'),
  drawStartDuelRed: (ctx, x, y) => drawStartR(ctx, x, y, 12, 'red'),
  drawStartDuelBlue: (ctx, x, y) => drawStartR(ctx, x, y, 12, 'blue'),
  drawShroom(ctx, x, y) {
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x, y, 8, 6, 0, 0, 2 * Math.PI);
    ctx.lineWidth = 2;
    ctx.fillStyle = '#0039ff';
    ctx.strokeStyle = '#001281';
    ctx.stroke();
    ctx.fill();
    // Add dots
    ctx.fillStyle = '#D3FDFC';
    for (const [dx, dy, r] of [[0, 5, 4], [-5, 0, 2], [5, 0, 2], [0, -2, 3]]) {
      ctx.beginPath();
      ctx.arc(x + dx, y + dy, r, 0, 2 * Math.PI);
      ctx.fill();
    }
    ctx.restore();
  },
  drawBowser: (ctx, x, y) => image(ctx, 'spaceBowser', x, y, 9),
  drawBowser3: (ctx, x, y) => image(ctx, 'spaceBowser3', x, y),
  drawItem2: (ctx, x, y) => image(ctx, 'spaceItem2', x, y, 9),
  drawItem3: (ctx, x, y) => image(ctx, 'spaceItem3', x, y),
  drawBattle2(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#099f0a', '#2e681e');
    // Zip zap
    ctx.beginPath();
    ctx.fillStyle = 'white';
    ctx.translate(x - 10, y - 10);
    ctx.moveTo(14, 3); // Top point
    ctx.lineTo(4, 11); // Left point
    ctx.lineTo(9, 11); // Go inward
    ctx.lineTo(7, 18); // Bottom point
    ctx.lineTo(16, 9); // Right point
    ctx.lineTo(12, 9); // Go inward
    ctx.lineTo(14, 3); // Back to top point
    ctx.fill();
    ctx.restore();
  },
  drawBattle3: (ctx, x, y) => image(ctx, 'spaceBattle3', x, y),
  drawBank2(ctx, x, y) {
    ctx.save();
    circle(ctx, x, y, 8, '#099f0a', '#2e681e');
    // Add fancy drawing of coin bag
    ctx.fillStyle = '#EEF700';
    ctx.translate(x - 10, y - 10);
    ctx.beginPath();
    ctx.arc(10, 12, 5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(8, 7);
    ctx.lineTo(7, 5);
    ctx.lineTo(8, 4);
    ctx.lineTo(12, 4);
    ctx.lineTo(13, 5);
    ctx.lineTo(12, 7);
    ctx.fill();
    ctx.fillStyle = '#099f0a';
    drawStarShape(ctx, 10, 12, 4, 5, 0.45);
    ctx.restore();
  },
  drawBank3: (ctx, x, y) => image(ctx, 'spaceBank3', x, y),
  drawArrow(ctx, x, y, game) {
    ctx.save();
    ctx.beginPath();
    ctx.fillStyle = '#F647A0';
    ctx.strokeStyle = '#94305B';
    if (game === 3) {
      ctx.translate(x - 12, y - 12);
      ctx.scale(1.25, 1.25);
    } else {
      ctx.translate(x - 10, y - 10);
    }
    ctx.moveTo(10, 1); // Top point
    ctx.lineTo(1, 10); // Left point
    ctx.lineTo(5, 10); // Go inward
    ctx.lineTo(5, 18); // Bottom left
    ctx.lineTo(15, 18); // Bottom right
    ctx.lineTo(15, 10); // Inner right
    ctx.lineTo(19, 10); // Right point
    ctx.lineTo(10, 1); // Back to top
    ctx.stroke();
    ctx.fill();
    ctx.restore();
  },
  drawBlackStar2(ctx, x, y) {
    ctx.save();
    // Transparent base circle
    circle(ctx, x, y, 8, 'rgba(0, 0, 0, 0.2)', 'rgba(0, 0, 0, 0.3)', 1);
    // Add black star on top
    ctx.fillStyle = 'black';
    drawStarShape(ctx, x, y, 9, 5, 0.45);
    ctx.restore();
  },
  drawGameGuy3: (ctx, x, y) => image(ctx, 'spaceGameGuy3', x, y),
  drawGameGuyDuel3: (ctx, x, y) => image(ctx, 'spaceGameGuyDuel3', x, y),
  drawDuelBasic: (ctx, x, y) => image(ctx, 'spaceDuelBasic3', x, y),
  drawDuelPowerup: (ctx, x, y) => image(ctx, 'spaceDuelPowerup3', x, y),
  drawDuelReverse: (ctx, x, y) => image(ctx, 'spaceDuelReverse3', x, y),
};
