/**
 * board/moves.js — Move selection, validation, execution, and AI moves
 *
 * Extracted from board.js: getVirtualBoard, queueAIMoveIfNeeded, selectPiece,
 * deselect, isPromotionMove, tryMove, executeMove, requestAIMove, onClick,
 * handleGameStatus.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function getVirtualBoard() {
    if (!CB.S.board || !CB.S.board.map) return [];
    let virtualBoard = CB.S.board.map(row => [...row]);
    if (CB.S.premoveQueue) {
      for (const pm of CB.S.premoveQueue) {
        const piece = virtualBoard[pm.from.r][pm.from.c];
        if (piece) {
          const targetEmpty = !virtualBoard[pm.to.r][pm.to.c];
          virtualBoard[pm.to.r][pm.to.c] = piece;
          virtualBoard[pm.from.r][pm.from.c] = null;

          if (piece.toLowerCase() === 'k' && Math.abs(pm.to.c - pm.from.c) === 2) {
            const isKingside = pm.to.c > pm.from.c;
            const rookColFrom = isKingside ? 7 : 0;
            const rookColTo = isKingside ? 5 : 3;
            const rook = virtualBoard[pm.from.r][rookColFrom];
            if (rook && rook.toLowerCase() === 'r') {
              virtualBoard[pm.from.r][rookColTo] = rook;
              virtualBoard[pm.from.r][rookColFrom] = null;
            }
          }

          if (piece.toLowerCase() === 'p' && pm.from.c !== pm.to.c && targetEmpty) {
            virtualBoard[pm.from.r][pm.to.c] = null;
          }

          if (piece.toLowerCase() === 'p' && (pm.to.r === 0 || pm.to.r === 7)) {
            const promotedPiece = piece === 'P' ? 'Q' : 'q';
            virtualBoard[pm.to.r][pm.to.c] = promotedPiece;
          }
        }
      }
    }
    return virtualBoard;
  }

  function queueAIMoveIfNeeded() {
    if (!CB.isAITurn || !CB.isAITurn() || CB.S.aiThinking) return;
    setTimeout(() => {
      if (CB.isAITurn && CB.isAITurn() && !CB.S.aiThinking && !CB.S.gameOver) {
        requestAIMove();
      }
    }, 200);
  }

  function deselect() {
    CB.S.selected = null;
    CB.S.hints = [];
    if (CB.refreshHighlights) CB.refreshHighlights();
  }

  function isPromotionMove(fr, fc, tr) {
    if (!CB.S.board || !CB.S.board[fr]) return false;
    const p = CB.S.board[fr][fc];
    if (!p) return false;
    return (p === 'P' && tr === 0) || (p === 'p' && tr === 7);
  }

  async function selectPiece(r, c) {
    const isPremoveMode = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor;
    const vBoard = isPremoveMode ? getVirtualBoard() : CB.S.board;
    if (!vBoard || !vBoard[r]) return;
    const p = vBoard[r][c];

    if (!p || CB.S.paused || CB.S.gameOver) return;

    CB.S.selected = { r, c };

    if (
      CB.S.gameMode === 'ai' &&
      CB.S.turn !== CB.S.playerColor &&
      CB.pColor(p) === CB.S.playerColor
    ) {
      CB.S.hints = [];
      if (CB.refreshHighlights) CB.refreshHighlights();
      return;
    }

    if (CB.computeLegalMovesClient) {
      const clientMoves = CB.computeLegalMovesClient(r, c);
      if (clientMoves !== null) {
        CB.S.hints = clientMoves;
        if (CB.refreshHighlights) CB.refreshHighlights();
        return;
      }
    }

    if (CB.get) {
      try {
        const data = await CB.get(`/api/valid-moves/?row=${r}&col=${c}`);
        CB.S.hints = data.valid_moves || [];
        if (CB.refreshHighlights) CB.refreshHighlights();
      } catch (e) {
        console.error("Error fetching valid moves:", e);
      }
    }
  }

  async function tryMove(fr, fc, tr, tc) {
    if (CB.S.paused || CB.S.gameOver) return;

    const isPremoveMode = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor;
    const vBoard = isPremoveMode ? getVirtualBoard() : CB.S.board;
    if (!vBoard || !vBoard[fr]) return;
    const p = vBoard[fr][fc];
    if (!p) return;

    if (
      CB.S.gameMode === 'ai' &&
      CB.pColor(p) === CB.S.playerColor &&
      CB.S.turn !== CB.S.playerColor
    ) {
      if (!CB.S.premoveQueue) CB.S.premoveQueue = [];
      CB.S.premoveQueue.push({
        from: { r: fr, c: fc },
        to: { r: tr, c: tc }
      });

      if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();
      if (CB.showStatus) CB.showStatus("Premove queued", false);

      CB.S.selected = null;
      CB.S.hints = [];
      if (CB.refreshHighlights) CB.refreshHighlights();

      return;
    }

    if (CB.pColor(p) !== CB.S.turn) {
      deselect();
      return;
    }

    if (fr === tr && fc === tc) {
      deselect();
      return;
    }

    if (isPromotionMove(fr, fc, tr)) {
      if (CB.animateMove) await CB.animateMove(fr, fc, tr, tc);

      CB.S.pendingPromo = { fr, fc, tr, tc };

      const color = CB.pColor(p);
      if (CB.showPromoModal) CB.showPromoModal(color);

      return;
    }

    await executeMove(fr, fc, tr, tc, null);
  }

  async function executeMove(fr, fc, tr, tc, promotionPiece, skipAnimation = false) {
    if (CB.S.isMoving) return { success: false, message: 'Move in progress' };
    CB.S.isMoving = true;
    try {
      if (typeof CB.S.openingTrainerMode !== 'undefined' && CB.S.openingTrainerMode) {
        const expectedMove = CB.S.openingTrainerSteps[CB.S.currentTrainerStep]?.expected_move;
        if (expectedMove) {
          const playedMove =
            `${String.fromCharCode(97 + fc)}${8 - fr}` +
            `${String.fromCharCode(97 + tc)}${8 - tr}`;

          if (playedMove.toLowerCase() !== expectedMove.toLowerCase()) {
            if (CB.showStatus) CB.showStatus(`Incorrect move. Expected: ${expectedMove}`, true);
            deselect();
            return { success: false, message: 'Incorrect move' };
          }
        }
      }

      const body = {
        from_row: fr, from_col: fc,
        to_row: tr, to_col: tc,
      };
      if (promotionPiece) body.promotion_piece = promotionPiece;

      const data = await CB.post('/api/move/', body);

      if (typeof CB.S.openingTrainerMode !== 'undefined' && CB.S.openingTrainerMode && data.valid) {
        CB.S.currentTrainerStep++;
        if (CB.S.currentTrainerStep >= CB.S.openingTrainerSteps.length) {
          CB.S.openingTrainerMode = false;
          if (CB.showStatus) CB.showStatus("Opening sequence completed!", false);
        }
      }

      if (data.valid) {
        CB.S.illegalMoveCount = 0;
        if (CB.playSound) CB.playSound(data);
        if (!skipAnimation && CB.animateMove) await CB.animateMove(fr, fc, tr, tc);
        if (CB.parseBoard) CB.S.board = CB.parseBoard(data.board);
        if (data.fen) CB.S.liveFen = data.fen;
        CB.S.turn = data.current_turn;

        const hasThreefoldWarning = data.threefold_warning;

        if (hasThreefoldWarning) {
          if (CB.showStatus) {
            CB.showStatus(
              '⚠️ This position has appeared twice. One more repetition will trigger a draw.',
              false
            );
          }
        }

        if (CB.S.dailyPuzzleMode && CB.S.currentPuzzle && !CB.S.puzzleAnalyzing) {
          const playedMove =
            `${String.fromCharCode(97 + fc)}${8 - fr}` +
            `${String.fromCharCode(97 + tc)}${8 - tr}`;

          const expectedMove = CB.S.currentPuzzle.solution[CB.S.puzzleMoveIndex];

          if (playedMove === expectedMove) {
            if (CB.clearPuzzleHints) CB.clearPuzzleHints();

            CB.S.puzzleMoveIndex++;
            CB.S.currentPuzzleFen = data.fen;
            CB.S.expectedMoveEval = null;
            if (CB.precalculateExpectedMoveEval) CB.precalculateExpectedMoveEval();

            if (CB.S.puzzleMoveIndex >= CB.S.currentPuzzle.solution.length) {
              const streak = CB.updatePuzzleStreak ? CB.updatePuzzleStreak() : 0;
              if (CB.updateStreakDisplay) CB.updateStreakDisplay();
              if (data.game_status === 'checkmate') {
              } else {
                if (CB.showConfirm) {
                  CB.showConfirm(
                    "🎉 Puzzle Solved!",
                    `🔥 Current Streak: ${streak}<br>🏆 Best Streak: ${(CB.getPuzzleStreak ? CB.getPuzzleStreak().longestStreak : 0)}<br>Come back tomorrow for a new challenge.`,
                    () => {
                      if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = "hidden";
                      if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.add("active");
                    },
                    "#f0c040"
                  );
                }
                return { success: true };
              }
            }
          } else {
            CB.S.puzzleAnalyzing = true;
            const origStatus = typeof document !== 'undefined' && document.getElementById("game-status")
              ? document.getElementById("game-status").textContent
              : "";
            if (CB.showStatus) CB.showStatus("Analyzing move with Stockfish...", false);

            if (CB.validateMoveWithStockfish) {
              CB.validateMoveWithStockfish(CB.S.currentPuzzleFen, data.fen, expectedMove)
                .then((isCorrect) => {
                  CB.S.puzzleAnalyzing = false;
                  if (CB.showStatus) CB.showStatus(origStatus, false);

                  if (isCorrect) {
                    CB.S.puzzleMoveIndex++;
                    CB.S.currentPuzzleFen = data.fen;
                    CB.S.expectedMoveEval = null;
                    if (CB.precalculateExpectedMoveEval) CB.precalculateExpectedMoveEval();

                    if (CB.S.puzzleMoveIndex >= CB.S.currentPuzzle.solution.length) {
                      const streak = CB.updatePuzzleStreak ? CB.updatePuzzleStreak() : 0;
                      if (CB.updateStreakDisplay) CB.updateStreakDisplay();
                      if (data.game_status === 'checkmate') {
                        CB.S.lastMove = { from: [fr, fc], to: [tr, tc] };
                        CB.S.whiteTime = data.white_time;
                        CB.S.blackTime = data.black_time;
                        if (CB.updatePlayerNames) CB.updatePlayerNames(data);
                        if (CB.updateTurn) CB.updateTurn();
                        if (CB.updateMoves) CB.updateMoves(data.move_history);
                        if (CB.updateCaptured) CB.updateCaptured(data.captured_pieces);
                        if (CB.syncPieces) CB.syncPieces();
                        if (CB.renderClocks) CB.renderClocks();
                        if (CB.updateMaterialUI) CB.updateMaterialUI(CB.S.board);
                        if (CB.endGame) return CB.endGame('checkmate', CB.S.turn).catch(e => console.error("Error in endGame:", e));
                      } else {
                        if (CB.showConfirm) {
                          CB.showConfirm(
                            "🎉 Puzzle Solved!",
                            `🔥 Current Streak: ${streak}<br>🏆 Best Streak: ${(CB.getPuzzleStreak ? CB.getPuzzleStreak().longestStreak : 0)}<br>Come back tomorrow for a new challenge.`,
                            () => {
                              if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = "hidden";
                              if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.add("active");
                            },
                            "#f0c040"
                          );
                        }
                      }
                    }
                  } else {
                    if (CB.showConfirm) {
                      CB.showConfirm(
                        "❌ Incorrect Move!",
                        "Would you like to try again?",
                        () => {
                          if (CB.startDailyPuzzle) CB.startDailyPuzzle();
                        },
                        "#ff4d4d"
                      );
                    }
                  }
                })
                .catch((err) => {
                  console.error("Stockfish validation promise error:", err);
                  CB.S.puzzleAnalyzing = false;
                  if (CB.showStatus) CB.showStatus(origStatus, false);
                  if (CB.showConfirm) {
                    CB.showConfirm(
                      "❌ Incorrect Move!",
                      "Would you like to try again?",
                      () => {
                        if (CB.startDailyPuzzle) CB.startDailyPuzzle();
                      },
                      "#ff4d4d"
                    );
                  }
                });
            }
            return { success: true };
          }
        }

        CB.S.lastMove = { from: [fr, fc], to: [tr, tc] };

        if (CB.S.gameMode === 'pvp' && CB.S.autoFlip) {
          CB.S.flipped = (CB.S.turn === 'black');
          if (CB.buildBoard) CB.buildBoard();
        }
        CB.S.whiteTime = data.white_time;
        CB.S.blackTime = data.black_time;

        CB.S.selected = null;
        CB.S.hints = [];
        if (CB.updatePlayerNames) CB.updatePlayerNames(data);
        if (CB.updateTurn) CB.updateTurn();
        if (CB.updateMoves) CB.updateMoves(data.move_history);
        if (CB.updateCaptured) CB.updateCaptured(data.captured_pieces);
        if (CB.syncPieces) CB.syncPieces();
        if (CB.renderClocks) CB.renderClocks();
        if (CB.startTimer) CB.startTimer();
        if (CB.updateMaterialUI) CB.updateMaterialUI(CB.S.board);
        let a11yMsg = '';
        const playedColor = CB.S.turn === 'white' ? 'Black' : 'White';
        if (data.captured) {
          const targetSquare = CB.getSquareLabel ? CB.getSquareLabel(tr, tc) : `${tr},${tc}`;
          const pieceCode = (typeof data.captured === 'string') ? data.captured : '';
          const pieceName = (CB.PIECE_NAMES && CB.PIECE_NAMES[pieceCode.toLowerCase()]) || 'piece';
          const capturer = playedColor;
          const capturedColor = capturer === 'White' ? 'Black' : 'White';
          a11yMsg = `${capturer} captured ${capturedColor}'s ${pieceName} on ${targetSquare}. `;
        } else if (data.move_history && data.move_history.length > 0) {
          const lastMv = data.move_history[data.move_history.length - 1].notation;
          if (typeof window !== 'undefined' && window.checkLessonMove && lastMv) {
            window.checkLessonMove(lastMv);
          }
          a11yMsg = `${playedColor} played ${lastMv}. `;
        }

        const gameEnded = handleGameStatus(data.game_status, data.draw_reason);
        if (!gameEnded) {
          if (data.game_status === 'check') {
            if (CB.applyCheckHighlight) CB.applyCheckHighlight();
            const checkMsg = CB.S.turn === 'white' ? 'Check to White King!' : 'Check to Black King!';
            a11yMsg += checkMsg;
          } else {
            if (CB.highlightCheck) CB.highlightCheck();
            if (!hasThreefoldWarning && CB.showStatus) {
              CB.showStatus('', false);
            }
          }
          if (a11yMsg && CB.announceMove) CB.announceMove(a11yMsg);
        }

        if (CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && !CB.S.gameOver) {
          requestAIMove();
        }
        return { success: true };
      } else {
        if (CB.showStatus) CB.showStatus(data.message, true);
        if (CB.flashBoard) CB.flashBoard();
        deselect();
        if (CB.S.premoveQueue && CB.S.premoveQueue.length > 0) {
          CB.S.premoveQueue = [];
          if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();
        }
        return { success: false, message: data.message };
      }
    } catch (e) {
      if (CB.handleReconnect) await CB.handleReconnect();
      return { success: false, message: 'Connection lost' };
    } finally {
      CB.S.isMoving = false;
    }
  }

  async function requestAIMove() {
    if (CB.S.gameOver || CB.S.aiThinking) return;
    const seq = ++CB.S.aiRequestSeq;
    CB.S.aiThinking = true;

    try {
      let piecesOnBoard = 0;
      if (CB.S.board) {
        for (let r = 0; r < 8; r++) {
          for (let c = 0; c < 8; c++) {
            if (CB.S.board[r][c]) piecesOnBoard++;
          }
        }
      }

      let delay;
      if (CB.S.currentDifficulty === 'easy') delay = 800 + Math.random() * (1500 - 800);
      else if (CB.S.currentDifficulty === 'hard') delay = 2500 + Math.random() * (4000 - 2500);
      else delay = 1500 + Math.random() * (2500 - 1500);
      await new Promise(resolve => setTimeout(resolve, delay));

      if (seq !== CB.S.aiRequestSeq) return;
      if (CB.S.gameOver) return;
      if (CB.S.paused) return;

      const data = await CB.post('/api/ai-move/', {});

      if (seq !== CB.S.aiRequestSeq) return;

      if (data.valid) {
        if (CB.playSound) CB.playSound(data);
        const mv = data.ai_move;

        if (CB.S.gameMode === 'analysis' && data.ai_move.predicted_responses && typeof document !== 'undefined') {
          const predPanel = document.getElementById('aiPredictionPanel');
          const predSuggestedMove = document.getElementById('predSuggestedMove');
          const predResponsesList = document.getElementById('predResponsesList');

          if (predPanel && predSuggestedMove && predResponsesList) {
            const formatEval = (val) => {
              if (val === undefined || val === null) return '';
              const v = (val / 100).toFixed(2);
              return `(${v > 0 ? '+' + v : v})`;
            };

            const moveText = mv.notation || (CB.getSquareLabel ? CB.getSquareLabel(mv.to_row, mv.to_col) : '');
            predSuggestedMove.textContent = '';
            const smStrong = document.createElement('strong');
            smStrong.textContent = moveText;
            predSuggestedMove.appendChild(smStrong);
            predSuggestedMove.appendChild(document.createTextNode(` ${formatEval(mv.eval)}`));

            predResponsesList.textContent = '';
            if (data.ai_move.predicted_responses.length === 0) {
              const li = document.createElement('li');
              li.textContent = 'No opponent response available. The position may be terminal.';
              predResponsesList.appendChild(li);
            } else {
              data.ai_move.predicted_responses.forEach((resp, index) => {
                const li = document.createElement('li');
                const respStrong = document.createElement('strong');
                respStrong.textContent = `${index + 1}. ${resp.notation}`;
                li.appendChild(respStrong);
                li.appendChild(document.createTextNode(` ${formatEval(resp.eval)}`));
                li.style.marginBottom = '5px';
                predResponsesList.appendChild(li);
              });
            }
            predPanel.style.display = 'block';
          }
        } else if (typeof document !== 'undefined') {
          const predPanel = document.getElementById('aiPredictionPanel');
          if (predPanel) predPanel.style.display = 'none';
        }

        if (CB.animateMove) await CB.animateMove(mv.from_row, mv.from_col, mv.to_row, mv.to_col);
        if (CB.parseBoard) CB.S.board = CB.parseBoard(data.board);
        if (data.fen) CB.S.liveFen = data.fen;
        CB.S.turn = data.current_turn;
        if (data.threefold_warning && CB.showStatus) {
          CB.showStatus(
            '⚠️ This position has appeared twice. One more repetition will trigger a draw.',
            false
          );
        }

        CB.S.lastMove = { from: [mv.from_row, mv.from_col], to: [mv.to_row, mv.to_col] };
        CB.S.whiteTime = data.white_time;
        CB.S.blackTime = data.black_time;

        CB.S.selected = null;
        CB.S.hints = [];
        if (CB.updatePlayerNames) CB.updatePlayerNames(data);
        if (CB.updateTurn) CB.updateTurn();
        if (CB.updateMoves) CB.updateMoves(data.move_history);
        if (CB.updateCaptured) CB.updateCaptured(data.captured_pieces);
        if (CB.syncPieces) CB.syncPieces();
        if (CB.renderClocks) CB.renderClocks();
        if (CB.startTimer) CB.startTimer();
        if (CB.updateMaterialUI) CB.updateMaterialUI(CB.S.board);
        let a11yMsg = '';
        const playedColor = CB.S.turn === 'white' ? 'Black' : 'White';
        if (data.captured) {
          const targetSquare = CB.getSquareLabel ? CB.getSquareLabel(mv.to_row, mv.to_col) : '';
          const pieceCode = (typeof data.captured === 'string') ? data.captured : '';
          const pieceName = (CB.PIECE_NAMES && CB.PIECE_NAMES[pieceCode.toLowerCase()]) || 'piece';
          const capturer = playedColor;
          const capturedColor = capturer === 'White' ? 'Black' : 'White';
          a11yMsg = `${capturer} captured ${capturedColor}'s ${pieceName} on ${targetSquare}. `;
        } else if (data.move_history && data.move_history.length > 0) {
          const lastMv = data.move_history[data.move_history.length - 1].notation;
          if (typeof window !== 'undefined' && window.checkLessonMove && lastMv) {
            window.checkLessonMove(lastMv);
          }
          a11yMsg = `AI played ${lastMv}. `;
        }

        const gameEnded = handleGameStatus(data.game_status, data.draw_reason);
        if (!gameEnded) {
          if (data.game_status === 'check') {
            if (CB.applyCheckHighlight) CB.applyCheckHighlight();
            const checkMsg = CB.S.turn === 'white' ? 'Check to White King!' : 'Check to Black King!';
            a11yMsg += checkMsg;
          } else {
            if (CB.highlightCheck) CB.highlightCheck();
            if (!data.threefold_warning && CB.showStatus) {
              CB.showStatus('Your turn.', false);
            }
          }
          if (a11yMsg && CB.announceMove) CB.announceMove(a11yMsg);

          if (CB.S.premoveQueue && CB.S.premoveQueue.length > 0) {
            const queued = CB.S.premoveQueue.shift();
            if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();

            const piece = CB.S.board[queued.from.r][queued.from.c];
            if (piece && CB.pColor(piece) === CB.S.turn) {
              setTimeout(() => {
                tryMove(queued.from.r, queued.from.c, queued.to.r, queued.to.c);
              }, 150);
            } else {
              CB.S.premoveQueue = [];
              if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();
              if (CB.showStatus) CB.showStatus("Premove cancelled: piece captured or invalid", true);
            }
          }
        }
      } else {
        if (CB.showStatus) CB.showStatus(data.message, true);
      }
    } catch (e) {
      if (CB.handleReconnect) await CB.handleReconnect();
    } finally {
      CB.S.aiThinking = false;
    }
  }

  async function onClick(r, c) {
    if (CB.S.replayMode || CB.S.viewingPastState) return;
    if (CB.S.isMoving || CB.S.isSanSubmitting) return;
    if (CB.S.dragging && !CB.S.touchDragging) return;

    const isPremoveMode = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor;
    const vBoard = isPremoveMode ? getVirtualBoard() : CB.S.board;
    if (!vBoard || !vBoard[r]) return;
    const piece = vBoard[r][c];

    const aiPremoveMode =
      CB.S.gameMode === 'ai' &&
      CB.S.turn !== CB.S.playerColor;

    if (CB.S.selected) {
      if (CB.S.selected.r === r && CB.S.selected.c === c) {
        return deselect();
      }

      if (aiPremoveMode) {
        if (!CB.S.premoveQueue) CB.S.premoveQueue = [];
        CB.S.premoveQueue.push({
          from: { r: CB.S.selected.r, c: CB.S.selected.c },
          to: { r, c }
        });

        if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();
        if (CB.showStatus) CB.showStatus("Premove queued", false);

        CB.S.selected = null;
        CB.S.hints = [];
        if (CB.refreshHighlights) CB.refreshHighlights();

        return;
      }

      if (CB.S.hints && CB.S.hints.some(h => h.row === r && h.col === c)) {
        return tryMove(CB.S.selected.r, CB.S.selected.c, r, c);
      }

      if (piece && CB.pColor(piece) === CB.S.turn) {
        return selectPiece(r, c);
      }

      return deselect();
    }

    if (
      piece &&
      (
        CB.pColor(piece) === CB.S.turn ||
        (
          aiPremoveMode &&
          CB.pColor(piece) === CB.S.playerColor
        )
      )
    ) {
      return selectPiece(r, c);
    }
  }

  function handleGameStatus(status, drawReason) {
    if (CB.S.dailyPuzzleMode && status !== 'checkmate') {
      return false;
    }
    if (status === 'checkmate') {
      if (CB.endGame) CB.endGame('checkmate', CB.S.turn).catch(e => console.error("Error in endGame:", e));
      return true;
    }
    if (status === 'stalemate') {
      if (CB.endGame) CB.endGame('stalemate', CB.S.turn).catch(e => console.error("Error in endGame:", e));
      return true;
    }
    if (status === 'draw') {
      if (CB.endGame) CB.endGame('draw', CB.S.turn, drawReason).catch(e => console.error("Error in endGame:", e));
      return true;
    }
    return false;
  }

  CB.getVirtualBoard = getVirtualBoard;
  CB.queueAIMoveIfNeeded = queueAIMoveIfNeeded;
  CB.selectPiece = selectPiece;
  CB.deselect = deselect;
  CB.isPromotionMove = isPromotionMove;
  CB.tryMove = tryMove;
  CB.executeMove = executeMove;
  CB.requestAIMove = requestAIMove;
  CB.onClick = onClick;
  CB.handleGameStatus = handleGameStatus;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      getVirtualBoard: getVirtualBoard,
      queueAIMoveIfNeeded: queueAIMoveIfNeeded,
      selectPiece: selectPiece,
      deselect: deselect,
      isPromotionMove: isPromotionMove,
      tryMove: tryMove,
      executeMove: executeMove,
      requestAIMove: requestAIMove,
      onClick: onClick,
      handleGameStatus: handleGameStatus
    };
  }
})();
