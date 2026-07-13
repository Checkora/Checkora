/**
 * board/endgame.js — Game end handling, session stats, and celebration effects
 *
 * Extracted from board.js: loadSessionStats, saveSessionStats,
 * renderSessionTracker, updateSessionTracker, recordGameResult,
 * loadGameCounter, saveGameCounter, renderGameCounter, updateGameCounterDisplay,
 * incrementGameCounter, endGame, createConfetti, createSparkles.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  const SESSION_STATS_KEY = 'checkoraSessionStats';
  const GAME_COUNTER_KEY = 'checkoraGameCounter';

  function loadSessionStats() {
    try {
      const raw = sessionStorage.getItem(SESSION_STATS_KEY);
      if (!raw) return { wins: 0, losses: 0, draws: 0 };
      const parsed = JSON.parse(raw);
      return {
        wins: Number(parsed.wins) || 0,
        losses: Number(parsed.losses) || 0,
        draws: Number(parsed.draws) || 0
      };
    } catch (e) {
      return { wins: 0, losses: 0, draws: 0 };
    }
  }

  function saveSessionStats(stats) {
    try {
      sessionStorage.setItem(SESSION_STATS_KEY, JSON.stringify(stats));
    } catch (e) {
      // sessionStorage unavailable
    }
  }

  function renderSessionTracker(stats) {
    if (typeof document === 'undefined') return;
    const winsEl = document.getElementById('sessionWins');
    const lossesEl = document.getElementById('sessionLosses');
    const drawsEl = document.getElementById('sessionDraws');
    if (winsEl) winsEl.textContent = stats.wins;
    if (lossesEl) lossesEl.textContent = stats.losses;
    if (drawsEl) drawsEl.textContent = stats.draws;
  }

  function updateSessionTracker() {
    renderSessionTracker(loadSessionStats());
  }

  function recordGameResult(outcome) {
    const stats = loadSessionStats();
    if (outcome === 'victory') stats.wins += 1;
    else if (outcome === 'defeat') stats.losses += 1;
    else if (outcome === 'draw') stats.draws += 1;
    else return;

    saveSessionStats(stats);
    renderSessionTracker(stats);
  }

  function loadGameCounter() {
    try {
      const raw = sessionStorage.getItem(GAME_COUNTER_KEY);
      const n = Number(raw);
      return Number.isFinite(n) && n > 0 ? n : 0;
    } catch (e) {
      return 0;
    }
  }

  function saveGameCounter(count) {
    try {
      sessionStorage.setItem(GAME_COUNTER_KEY, String(count));
    } catch (e) {
      // sessionStorage unavailable
    }
  }

  function renderGameCounter(count) {
    if (typeof document === 'undefined') return;
    const counterEl = document.getElementById('game-counter');
    if (counterEl) counterEl.textContent = `Game #${count}`;
  }

  function updateGameCounterDisplay() {
    renderGameCounter(loadGameCounter() || 1);
  }

  function incrementGameCounter() {
    const count = loadGameCounter() + 1;
    saveGameCounter(count);
    renderGameCounter(count);
    return count;
  }

  async function endGame(reason, loserColor, drawReason = null) {
    if (CB.S.gameOver) return;
    CB.S.gameOver = true;

    let title = '', message = '';
    let isCelebration = false;

    try {
      const frozenPlayerColor = CB.S.playerColor;
      CB.S.replayMode = true;
      CB.S.paused = true;
      if (typeof clearInterval !== 'undefined') clearInterval(CB.S.timerInterval);

      if (CB.S.blindfoldMode && typeof document !== 'undefined') {
        CB.S.blindfoldMode = false;
        document.body.classList.remove('blindfold-mode');
        const blindfoldBtn = document.getElementById('blindfoldBtn');
        if (blindfoldBtn) blindfoldBtn.textContent = 'Blindfold: OFF';
      }
      if (CB.updateThinkingDots) CB.updateThinkingDots();

      title = ''; message = '';

      const isWon = reason === 'checkmate' || reason === 'resign' || reason === 'timeout';
      const winnerColor = isWon ? (loserColor === 'white' ? 'black' : 'white') : null;

      let resultState = 'draw';
      if (isWon) {
        if (CB.S.gameMode === 'ai') {
          resultState = (winnerColor === frozenPlayerColor) ? 'victory' : 'defeat';
        } else {
          resultState = 'victory';
        }
      }

      isCelebration = (resultState === 'victory');

      if (CB.S.gameMode === 'ai' || reason === 'draw' || reason === 'stalemate') {
        recordGameResult(resultState);
      }

      if (CB.playGameOverSound) CB.playGameOverSound(reason, resultState);

      if (typeof document !== 'undefined') {
        if (reason === 'checkmate') {
          const winnerName = loserColor === 'white' ? (CB.DOM.blackNameLabel?.textContent || 'Black') : (CB.DOM.whiteNameLabel?.textContent || 'White');
          title = 'Checkmate';
          message = `${winnerName} Wins!`;
        } else if (reason === 'stalemate') {
          title = 'Stalemate';
          message = 'The game is a draw.';
        } else if (reason === 'draw') {
          title = 'Draw';
          const drawMessages = {
            agreement: 'Draw by agreement.',
            threefold_repetition: 'Draw by repetition.',
            fifty_move_rule: 'Draw by fifty-move rule.',
            insufficient_material: 'Draw by insufficient material.',
          };
          message = drawMessages[drawReason] || 'The game is a draw.';
        } else if (reason === 'resign') {
          const winnerName = loserColor === 'white' ? (CB.DOM.blackNameLabel?.textContent || 'Black') : (CB.DOM.whiteNameLabel?.textContent || 'White');
          const loserName = loserColor === 'white' ? (CB.DOM.whiteNameLabel?.textContent || 'White') : (CB.DOM.blackNameLabel?.textContent || 'Black');
          title = 'Victory';
          message = `${loserName} resigned. ${winnerName} Wins!`;
        } else if (reason === 'timeout') {
          const winnerName = loserColor === 'white' ? (CB.DOM.blackNameLabel?.textContent || 'Black') : (CB.DOM.whiteNameLabel?.textContent || 'White');
          const loserName = loserColor === 'white' ? (CB.DOM.whiteNameLabel?.textContent || 'White') : (CB.DOM.blackNameLabel?.textContent || 'Black');
          title = 'Timeout';
          message = `${loserName} ran out of time. ${winnerName} Wins!`;
        }
      }

      if (CB.DOM.resignBtn) CB.DOM.resignBtn.style.display = 'none';
      if (CB.DOM.drawBtn) CB.DOM.drawBtn.style.display = 'none';
      if (CB.DOM.pauseBtn) CB.DOM.pauseBtn.style.display = 'none';
      if (CB.DOM.newPvPBtn) CB.DOM.newPvPBtn.style.display = '';
      if (CB.DOM.newAIBtn) CB.DOM.newAIBtn.style.display = '';
      if (CB.DOM.dailyPuzzleBtn) CB.DOM.dailyPuzzleBtn.style.display = '';
      if (CB.DOM.newFenBtn) CB.DOM.newFenBtn.style.display = '';

      let durationText = '';

      if (CB.S.gameStartTime) {
        const duration = Date.now() - CB.S.gameStartTime;
        durationText = CB.formatGameDuration ? CB.formatGameDuration(duration) : '';
      }

      CB.S.replayMoves = [];
      CB.S.rawAnalysisMoves = [];
      CB.S.replayIndex = 0;

      if (typeof document !== 'undefined') {
        const moveRows = Array.from(document.querySelectorAll('.move-row')).reverse();

        moveRows.forEach(row => {
          const spans = row.querySelectorAll('.move-white, .move-black');
          spans.forEach(span => {
            const rawMove = span.textContent?.replace(/\s+/g, '')?.trim();
            if (rawMove && rawMove !== '...') {
              CB.S.rawAnalysisMoves.push(rawMove);
            }

            const move = span.textContent
              ?.replace(/[+#]/g, '')
              ?.replace(/\s+/g, '')
              ?.trim();

            if (move && move !== '...') {
              CB.S.replayMoves.push(move);
            }
          });
        });
      }

      if (typeof window !== 'undefined' && window.Chess) {
        CB.S.replayBoard = new window.Chess();
      }
      if (CB.resetReplayBoard) CB.resetReplayBoard();

      if (CB.DOM.replayControls) {
        CB.DOM.replayControls.classList.remove('hidden');
      }

      if (typeof document !== 'undefined') {
        const bannerEl = document.getElementById('gameOverBanner');
        const bannerIconEl = document.getElementById('bannerIcon');

        if (bannerEl) {
          bannerEl.className = 'result-banner';
          if (resultState === 'victory') {
            bannerEl.classList.add('banner-victory');
            if (bannerIconEl) bannerIconEl.textContent = '🏆';
            if (CB.DOM.gameOverTitle) CB.DOM.gameOverTitle.textContent = 'VICTORY';
          } else if (resultState === 'defeat') {
            bannerEl.classList.add('banner-defeat');
            if (bannerIconEl) bannerIconEl.textContent = '💀';
            if (CB.DOM.gameOverTitle) CB.DOM.gameOverTitle.textContent = 'DEFEAT';
          } else {
            bannerEl.classList.add('banner-draw');
            if (bannerIconEl) bannerIconEl.textContent = '🤝';
            if (CB.DOM.gameOverTitle) CB.DOM.gameOverTitle.textContent = 'DRAW';
          }
        }

        const messageEl = CB.DOM.gameOverMessage || document.getElementById('gameOverMessage');
        if (messageEl) {
          messageEl.textContent = message;
        }

        const illustrationEl = document.getElementById('gameOverIllustration');
        if (illustrationEl) {
          let svgContent = '';
          if (resultState === 'defeat') {
            if (reason === 'timeout') {
              svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M10 80 H90 L80 90 H20 Z" fill="#252545" opacity="0.6"/>
                                            <g class="svg-animate-hourglass">
                                                <path d="M35 20 H65 V30 L55 50 L65 70 V80 H35 V70 L45 50 L35 30 Z" fill="#7f8c8d" stroke="#5c6466" stroke-width="2"/>
                                                <path d="M38 25 H62 V28 L52 48 L48 48 L38 28 Z" fill="#95a5a6"/>
                                                <path d="M48 52 L52 52 L62 72 V75 H38 V72 Z" fill="#cbd5e0"/>
                                                <circle cx="50" cy="62" r="3" fill="#ffffff"/>
                                            </g>
                                        </svg>
                                    `;
            } else if (reason === 'checkmate') {
              svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M10 80 H90 L80 90 H20 Z" fill="#2d1e1e" opacity="0.6"/>
                                            <g class="svg-animate-crown" transform="rotate(15 50 60)">
                                                <path d="M35 60 L40 35 L50 48 L60 35 L65 60 Z" fill="#7f8c8d" stroke="#5c6466" stroke-width="2"/>
                                                <circle cx="40" cy="33" r="2.5" fill="#95a5a6"/>
                                                <circle cx="50" cy="46" r="2.5" fill="#95a5a6"/>
                                                <circle cx="60" cy="33" r="2.5" fill="#95a5a6"/>
                                                <rect x="33" y="60" width="34" height="6" rx="2" fill="#5c6466"/>
                                                <rect x="37" y="66" width="26" height="4" fill="#3e4445"/>
                                            </g>
                                        </svg>
                                    `;
            } else {
              svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="35" y="20" width="4" height="65" fill="#5c6466" rx="2"/>
                                            <g class="svg-animate-flag">
                                                <path d="M39 22 C48 18, 52 26, 65 22 C72 20, 75 23, 75 32 C75 42, 65 38, 55 42 C45 46, 39 38, 39 38 Z" fill="#7f8c8d" stroke="#5c6466" stroke-width="1"/>
                                            </g>
                                            <path d="M20 78 L23 68 L28 73 L33 68 L36 78 Z" fill="#95a5a6" transform="rotate(-15 20 78)"/>
                                        </svg>
                                    `;
            }
          } else if (resultState === 'draw') {
            svgContent = `
                                    <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <g class="svg-animate-handshake" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                            <path d="M15 50 H30 L45 40 L50 48 L40 55 H25" stroke="#3498db" stroke-width="4"/>
                                            <path d="M85 50 H70 L55 40 L50 48 L60 55 H75" stroke="#ffd700" stroke-width="4"/>
                                            <path d="M45 44 L48 52" stroke="#ffffff" stroke-width="3"/>
                                            <path d="M52 44 L55 52" stroke="#ffffff" stroke-width="3"/>
                                        </g>
                                        <circle cx="50" cy="50" r="35" stroke="rgba(255,255,255,0.06)" stroke-width="2" stroke-dasharray="4 4"/>
                                    </svg>
                                `;
          } else {
            if (reason === 'checkmate') {
              svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M10 80 H90 L80 90 H20 Z" fill="#252545" opacity="0.6"/>
                                            <g class="svg-animate-crown">
                                                <path d="M35 60 L40 35 L50 48 L60 35 L65 60 Z" fill="#ffd700" stroke="#b89000" stroke-width="2"/>
                                                <circle cx="40" cy="33" r="2.5" fill="#ffffff"/>
                                                <circle cx="50" cy="46" r="2.5" fill="#ffffff"/>
                                                <circle cx="60" cy="33" r="2.5" fill="#ffffff"/>
                                                <rect x="33" y="60" width="34" height="6" rx="2" fill="#d4af37"/>
                                                <rect x="37" y="66" width="26" height="4" fill="#a08020"/>
                                            </g>
                                        </svg>
                                    `;
            } else if (reason === 'timeout') {
              svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="20" y="30" width="60" height="50" rx="8" fill="#1b1b32" stroke="#444" stroke-width="3"/>
                                            <circle cx="38" cy="55" r="16" fill="#111" stroke="#f0c040" stroke-width="2"/>
                                            <circle cx="38" cy="55" r="14" fill="#222"/>
                                            <line x1="38" y1="55" x2="38" y2="45" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
                                            <line x1="38" y1="55" x2="46" y2="55" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
                                            <g class="svg-animate-flag">
                                                <rect x="68" y="24" width="4" height="25" fill="#777"/>
                                                <path d="M68 28 L52 35 L68 42 Z" fill="#ef4444"/>
                                            </g>
                                        </svg>
                                    `;
            } else {
              svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="35" y="20" width="4" height="65" fill="#777" rx="2"/>
                                            <g class="svg-animate-flag">
                                                <path d="M39 22 C48 18, 52 26, 65 22 C72 20, 75 23, 75 32 C75 42, 65 38, 55 42 C45 46, 39 38, 39 38 Z" fill="#ffffff" stroke="#ddd" stroke-width="1"/>
                                                <path d="M45 27 H55 M45 33 H65" stroke="#eee" stroke-width="1.5" stroke-linecap="round"/>
                                            </g>
                                            <path d="M20 78 L23 68 L28 73 L33 68 L36 78 Z" fill="#d4af37" transform="rotate(-15 20 78)"/>
                                        </svg>
                                    `;
            }
          }
          illustrationEl.innerHTML = svgContent;
        }

        const resReasonEl = document.getElementById('resSummaryReason');
        if (resReasonEl) {
          let reasonText = 'Draw';
          if (reason === 'checkmate') reasonText = 'Checkmate';
          else if (reason === 'resign') reasonText = 'Resigned';
          else if (reason === 'timeout') reasonText = 'Timeout';
          else if (reason === 'stalemate') reasonText = 'Stalemate';
          else if (reason === 'draw') {
            const drawLabels = {
              agreement: 'Draw (Agreement)',
              threefold_repetition: 'Draw (Repetition)',
              fifty_move_rule: 'Draw (50-move)',
              insufficient_material: 'Draw (Material)',
            };
            reasonText = drawLabels[drawReason] || 'Draw';
          }
          resReasonEl.textContent = reasonText;
        }

        const resMovesEl = document.getElementById('resSummaryMoves');
        if (resMovesEl) {
          const fullMoves = Math.ceil(CB.S.replayMoves.length / 2);
          resMovesEl.textContent = `${fullMoves} ${fullMoves === 1 ? 'move' : 'moves'}`;
        }

        const durationElement = document.getElementById('gameDurationText');
        if (durationElement) {
          durationElement.textContent = durationText || '00:00';
        }

        const matRes = CB.calculateMaterial ? CB.calculateMaterial(CB.S.board) : { white: 0, black: 0 };
        const whiteMat = matRes.white;
        const blackMat = matRes.black;
        const resMatDiffEl = document.getElementById('resMaterialDiff');
        if (resMatDiffEl) {
          if (whiteMat === blackMat) {
            resMatDiffEl.textContent = 'Even';
          } else if (whiteMat > blackMat) {
            resMatDiffEl.textContent = `White +${whiteMat - blackMat}`;
          } else {
            resMatDiffEl.textContent = `Black +${blackMat - whiteMat}`;
          }
        }

        const modalWhiteCap = document.getElementById('modalWhiteCaptured');
        const modalBlackCap = document.getElementById('modalBlackCaptured');
        if (modalWhiteCap && CB.DOM.wCapEl) {
          modalWhiteCap.innerHTML = '';
          Array.from(CB.DOM.wCapEl.children).forEach(child => {
            modalWhiteCap.appendChild(child.cloneNode(true));
          });
        }
        if (modalBlackCap && CB.DOM.bCapEl) {
          modalBlackCap.innerHTML = '';
          Array.from(CB.DOM.bCapEl.children).forEach(child => {
            modalBlackCap.appendChild(child.cloneNode(true));
          });
        }

        const achievementsListEl = document.getElementById('resAchievementsList');
        const achievementsSectionEl = document.getElementById('resAchievementsSection');

        if (achievementsListEl) {
          achievementsListEl.innerHTML = '';
          const badges = [];

          if (reason === 'timeout') badges.push({ text: 'Won on Time', icon: '⏱️' });
          if (reason === 'checkmate') badges.push({ text: 'Master Tactician', icon: '🧩' });

          let hasWhiteQueen = false;
          let hasBlackQueen = false;
          for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
              if (CB.S.board[r][c] === 'Q') hasWhiteQueen = true;
              if (CB.S.board[r][c] === 'q') hasBlackQueen = true;
            }
          }

          const wPoints = parseInt(document.getElementById('whitePoints')?.textContent.replace('+', '')) || 0;
          const bPoints = parseInt(document.getElementById('blackPoints')?.textContent.replace('+', '')) || 0;

          if (isWon) {
            if (winnerColor === 'white' && hasWhiteQueen) {
              badges.push({ text: 'Queen Survived', icon: '👑' });
            } else if (winnerColor === 'black' && hasBlackQueen) {
              badges.push({ text: 'Queen Survived', icon: '👑' });
            }

            if (CB.S.replayMoves.length <= 30) {
              badges.push({ text: 'Lightning Fast', icon: '⚡' });
            }

            if (winnerColor === 'white' && wPoints >= 15) {
              badges.push({ text: 'Fierce Attacker', icon: '⚔️' });
            } else if (winnerColor === 'black' && bPoints >= 15) {
              badges.push({ text: 'Fierce Attacker', icon: '⚔️' });
            }
          } else {
            if (whiteMat < blackMat) {
              badges.push({ text: 'Resilient Defense (White)', icon: '🛡️' });
            } else if (blackMat < whiteMat) {
              badges.push({ text: 'Resilient Defense (Black)', icon: '🛡️' });
            }
          }

          if (badges.length === 0) {
            badges.push({ text: 'Good Game', icon: '🤝' });
          }

          badges.forEach(badge => {
            const badgeDiv = document.createElement('div');
            badgeDiv.className = 'achievement-badge';
            badgeDiv.innerHTML = `<span class="achievement-badge-icon">${badge.icon}</span> ${badge.text}`;
            achievementsListEl.appendChild(badgeDiv);
          });

          if (achievementsSectionEl) {
            achievementsSectionEl.style.display = 'block';
          }
        }
      }

      let fenHistory = [];
      if (typeof window !== 'undefined' && window.Chess) {
        try {
          let tempChess = new window.Chess();
          fenHistory.push(tempChess.fen());
          for (let move of CB.S.replayMoves) {
            let res = tempChess.move(move);
            if (!res) break;
            fenHistory.push(tempChess.fen());
          }
        } catch (e) {
          console.error("Error replaying moves for history", e);
        }
      }

      const currentAnalysisSeq = ++CB.S.analysisRequestSeq;

      if (CB.post) {
        CB.post('/api/analyze-game/', {
          moves: CB.S.rawAnalysisMoves,
          fen_history: fenHistory,
          result: resultState,
          reason: reason
        }).then(analysisData => {
          if (!analysisData) return;
          if (currentAnalysisSeq !== CB.S.analysisRequestSeq) return;
          if (typeof document === 'undefined') return;

          const openingNameEl = document.getElementById('resOpeningName');
          if (openingNameEl) {
            openingNameEl.textContent = analysisData.opening || 'Standard Game';
          }

          const capEl = document.getElementById('resAnalysisCaptures');
          if (capEl) capEl.textContent = analysisData.captures || 0;

          const chkEl = document.getElementById('resAnalysisChecks');
          if (chkEl) chkEl.textContent = analysisData.checks || 0;

          const matEl = document.getElementById('resAnalysisCheckmates');
          if (matEl) matEl.textContent = analysisData.checkmates || 0;

          const proEl = document.getElementById('resAnalysisPromotions');
          if (proEl) proEl.textContent = analysisData.promotions || 0;

          const accuracyEl = document.getElementById('resAccuracyScore');
          const panelAccuracyEl = document.getElementById('panelAccuracyScore');
          if (accuracyEl && analysisData.accuracy !== undefined) {
            accuracyEl.textContent = `${analysisData.accuracy}%`;
            if (panelAccuracyEl) panelAccuracyEl.textContent = `${analysisData.accuracy}%`;
          }

          const mistakesEl = document.getElementById('resMistakesCount');
          if (mistakesEl && analysisData.mistakes !== undefined) {
            mistakesEl.textContent = analysisData.mistakes;
          }

          const blundersEl = document.getElementById('resBlundersCount');
          const panelBlundersEl = document.getElementById('panelBlundersCount');
          if (blundersEl && analysisData.blunders !== undefined) {
            blundersEl.textContent = analysisData.blunders;
            if (panelBlundersEl) panelBlundersEl.textContent = analysisData.blunders;
          }

          const tbody = document.getElementById('postGameAnalysisTableBody');
          if (tbody && analysisData.move_analysis_details) {
            tbody.innerHTML = '';
            analysisData.move_analysis_details.forEach(detail => {
              const tr = document.createElement('tr');
              tr.style.borderBottom = '1px solid #333';

              const tdMove = document.createElement('td');
              tdMove.style.padding = '5px';
              tdMove.textContent = detail.move_num;
              tr.appendChild(tdMove);

              const tdPlayed = document.createElement('td');
              tdPlayed.style.padding = '5px';
              tdPlayed.textContent = detail.played;
              tr.appendChild(tdPlayed);

              const tdBest = document.createElement('td');
              tdBest.style.padding = '5px';
              tdBest.textContent = detail.best;
              tr.appendChild(tdBest);

              const tdClass = document.createElement('td');
              tdClass.style.padding = '5px';
              tdClass.style.color = detail.class === 'Best' ? '#4caf50' : '#f44336';
              tdClass.textContent = detail.class;
              tr.appendChild(tdClass);

              tbody.appendChild(tr);
            });
          }

          const bestMoveEl = document.getElementById('resBestMove');
          if (bestMoveEl) {
            if (analysisData.move_analysis_details && analysisData.move_analysis_details.length > 0) {
              const bestMoves = analysisData.move_analysis_details.filter(d => d.class === 'Best');
              if (bestMoves.length > 0) {
                const lastBest = bestMoves[bestMoves.length - 1];
                bestMoveEl.textContent = `${lastBest.played} (Best)`;
              } else if (CB.S.rawAnalysisMoves.length > 2) {
                bestMoveEl.textContent = `${CB.S.rawAnalysisMoves[2]} (Book)`;
              } else {
                bestMoveEl.textContent = 'Standard Game';
              }
            } else {
              bestMoveEl.textContent = 'Standard Game';
            }
          }

          const blunderEl = document.getElementById('resBlunder');
          if (blunderEl) {
            const blunderLabel = blunderEl.previousElementSibling;
            if (analysisData.blunders > 0) {
              blunderEl.textContent = `${analysisData.blunders} Blunder${analysisData.blunders > 1 ? 's' : ''}`;
              if (blunderLabel) blunderLabel.textContent = 'Blunder';
            } else if (analysisData.mistakes > 0) {
              blunderEl.textContent = `${analysisData.mistakes} Mistake${analysisData.mistakes > 1 ? 's' : ''}`;
              if (blunderLabel) blunderLabel.textContent = 'Mistake';
            } else {
              blunderEl.textContent = 'None';
              if (blunderLabel) blunderLabel.textContent = 'Blunder';
            }
          }
        }).catch(e => {
          console.error("Failed to fetch post-game analysis", e);
        });
      }
    } catch (error) {
      console.error("Error during endGame setup:", error);
      if (!title) title = 'Game Over';
      if (!message) message = 'The game has ended.';
      isCelebration = false;
    }

    if (typeof setTimeout !== 'undefined') {
      setTimeout(() => {
        if (typeof document === 'undefined') return;
        const overlayEl = CB.DOM.gameOverOverlay || document.getElementById('gameOverOverlay');
        if (!overlayEl) return;
        if (isCelebration) {
          overlayEl.classList.add('game-over-celebration');
          createConfetti();
          createSparkles();
        } else {
          overlayEl.classList.remove('game-over-celebration');
        }

        overlayEl.style.transition = 'opacity 0.5s ease-in-out';
        overlayEl.style.opacity = '0';
        overlayEl.classList.add('active');

        setTimeout(() => {
          if (overlayEl) overlayEl.style.opacity = '1';
        }, 500);
      }, 500);
    }

    if (CB.showStatus) CB.showStatus(title + ': ' + message, false);

    const winnerColorText = loserColor === 'white' ? 'Black' : 'White';
    let cleanMsg = '';
    if (reason === 'checkmate') {
      cleanMsg = `Checkmate. ${winnerColorText} wins!`;
    } else if (reason === 'resign') {
      const resigningColorText = loserColor === 'white' ? 'White' : 'Black';
      cleanMsg = `${resigningColorText} has resigned. ${winnerColorText} wins!`;
    } else if (reason === 'timeout') {
      const timeoutColorText = loserColor === 'white' ? 'White' : 'Black';
      cleanMsg = `${timeoutColorText} ran out of time. ${winnerColorText} wins!`;
    } else if (reason === 'stalemate') {
      cleanMsg = 'Game drawn by stalemate.';
    } else if (reason === 'draw') {
      if (drawReason === 'agreement') {
        cleanMsg = 'Game drawn by agreement.';
      } else if (drawReason === 'threefold_repetition') {
        cleanMsg = 'Game drawn by threefold repetition.';
      } else if (drawReason === 'fifty_move_rule') {
        cleanMsg = 'Game drawn by fifty-move rule.';
      } else if (drawReason === 'insufficient_material') {
        cleanMsg = 'Game drawn by insufficient material.';
      } else {
        cleanMsg = 'Game drawn by agreement / stalemate / threefold repetition.';
      }
    } else {
      cleanMsg = 'Game drawn by agreement / stalemate / threefold repetition.';
    }
    if (CB.announceMove) CB.announceMove(cleanMsg);

    if (typeof document !== 'undefined') {
      document.title = 'Game Over - Checkora';
    }
  }

  function createConfetti() {
    if (typeof document === 'undefined') return;
    const overlay = document.getElementById('gameOverOverlay');
    if (!overlay) return;
    const dialog = overlay.querySelector('.promo-dialog');
    if (!dialog) return;

    let confettiContainer = dialog.querySelector('.confetti-container');
    if (!confettiContainer) {
      confettiContainer = document.createElement('div');
      confettiContainer.className = 'confetti-container';
      dialog.style.position = 'relative';
      dialog.appendChild(confettiContainer);
    }

    confettiContainer.innerHTML = '';
    const colors = ['#ffd700', '#f0c040', '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ff9ff3'];
    const confettiCount = 50;

    for (let i = 0; i < confettiCount; i++) {
      const confetti = document.createElement('div');
      confetti.className = 'confetti';

      const randomColor = colors[Math.floor(Math.random() * colors.length)];
      const randomLeft = Math.random() * 100;
      const randomDelay = Math.random() * 0.5;
      const randomDuration = 2 + Math.random() * 2;
      const randomRotation = Math.random() * 360;

      confetti.style.left = randomLeft + '%';
      confetti.style.background = randomColor;
      confetti.style.animationDelay = randomDelay + 's';
      confetti.style.animationDuration = randomDuration + 's';
      confetti.style.transform = `rotate(${randomRotation}deg)`;

      if (Math.random() > 0.5) {
        confetti.style.borderRadius = '50%';
      }

      confettiContainer.appendChild(confetti);
    }
  }

  function createSparkles() {
    if (typeof document === 'undefined') return;
    const overlay = document.getElementById('gameOverOverlay');
    if (!overlay) return;
    const dialog = overlay.querySelector('.promo-dialog');
    if (!dialog) return;

    let confettiContainer = dialog.querySelector('.confetti-container');
    if (!confettiContainer) {
      confettiContainer = document.createElement('div');
      confettiContainer.className = 'confetti-container';
      dialog.style.position = 'relative';
      dialog.appendChild(confettiContainer);
    }

    const sparkleCount = 20;

    for (let i = 0; i < sparkleCount; i++) {
      const sparkle = document.createElement('div');
      sparkle.className = 'sparkle';

      const randomLeft = Math.random() * 100;
      const randomTop = Math.random() * 100;
      const randomDelay = Math.random() * 1.5;

      sparkle.style.left = randomLeft + '%';
      sparkle.style.top = randomTop + '%';
      sparkle.style.animationDelay = randomDelay + 's';

      confettiContainer.appendChild(sparkle);
    }
  }

  CB.loadSessionStats = loadSessionStats;
  CB.saveSessionStats = saveSessionStats;
  CB.renderSessionTracker = renderSessionTracker;
  CB.updateSessionTracker = updateSessionTracker;
  CB.recordGameResult = recordGameResult;
  CB.loadGameCounter = loadGameCounter;
  CB.saveGameCounter = saveGameCounter;
  CB.renderGameCounter = renderGameCounter;
  CB.updateGameCounterDisplay = updateGameCounterDisplay;
  CB.incrementGameCounter = incrementGameCounter;
  CB.endGame = endGame;
  CB.createConfetti = createConfetti;
  CB.createSparkles = createSparkles;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      loadSessionStats: loadSessionStats,
      saveSessionStats: saveSessionStats,
      renderSessionTracker: renderSessionTracker,
      updateSessionTracker: updateSessionTracker,
      recordGameResult: recordGameResult,
      loadGameCounter: loadGameCounter,
      saveGameCounter: saveGameCounter,
      renderGameCounter: renderGameCounter,
      updateGameCounterDisplay: updateGameCounterDisplay,
      incrementGameCounter: incrementGameCounter,
      endGame: endGame,
      createConfetti: createConfetti,
      createSparkles: createSparkles
    };
  }
})();
