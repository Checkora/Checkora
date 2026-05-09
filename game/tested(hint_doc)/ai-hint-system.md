# AI Hint System – Contributor Notes

## Overview
This feature introduces an AI-powered hint system for the chess board. The system uses the existing AI engine to suggest strategic moves to the player without automatically executing the move.

The hint system currently:
- Highlights the suggested source square
- Highlights the suggested destination square
- Uses visual glow effects for move guidance
- Limits hint usage to preserve gameplay balance
- Disables the hint button after the allowed limit is reached
- Resets hint availability when a new game starts

---

# Gameplay Logic

## Hint Limit
The current implementation uses a shared strategic hint pool for the entire match.

### Current Limit
- Total hints per match: 3

### Reasoning
The shared hint pool was intentionally designed to:
- Prevent excessive AI engine computations
- Reduce unnecessary backend load
- Avoid turning gameplay into “AI vs AI”
- Encourage strategic usage of hints
- Preserve game difficulty and player decision-making

---

# AI Hint Flow

1. Player presses the `Hint` button
2. Frontend sends a request to:
   `/api/hint/`
3. Backend calls:
   `get_ai_move()`
4. Best move coordinates are returned
5. Frontend visually highlights:
   - Suggested source square
   - Suggested destination square
6. The move is NOT automatically executed

---

# UI/UX Features

## Visual Guidance
The system currently supports:
- Source square highlighting
- Destination square highlighting
- Glow-based move suggestion effects

## Button State Handling
- Hint counter updates dynamically
- Button becomes disabled after limit is reached
- Disabled button uses visual freeze/grey styling

---

# Known Observations

During testing, occasional AI instability was observed:
- AI may stop responding after several moves
- Engine may occasionally return:
  `"No legal moves available."`
  even in playable positions

Based on current testing, this behavior appears related to the existing AI engine or engine communication layer rather than the frontend hint implementation itself.

The hint system may expose this issue more frequently because it increases AI analysis requests during gameplay.

---

# Possible Cause

The current AI system appears to use the same computation pipeline for:
- Actual AI move generation
- Hint analysis requests

Repeated hint requests may therefore affect:
- Engine computation state
- Shared subprocess communication
- AI response stability

This is currently treated as an existing engine-side architectural concern rather than a frontend gameplay issue.

---

# Suggested Future Improvements

## Gameplay Improvements
- Separate hint pools for White and Black in PvP mode
- Different hint logic for PvP and AI modes
- Difficulty-scaled hint limits
- Unlockable hints using coins or rewards
- Reward-based hints using ads or achievements

---

# UI/UX Improvements
- Animated glow transitions
- Customizable hint effects
- Dynamic move path indicators
- Theme-based highlight styles

---

# Engine Improvements
- Lightweight AI search depth for hints
- Separate engine depth for AI moves vs hint calculations
- Better AI timeout handling
- Engine response caching
- Improved engine recovery and stability handling

---

# Architectural Notes

The frontend hint system intentionally avoids:
- Direct move execution
- Board mutation during hint generation
- Turn manipulation

This keeps the feature relatively isolated from core gameplay execution logic and reduces the risk of corrupting active game state.

---

# Contributor Notes

Future contributors working on this feature should carefully test:
- AI mode gameplay
- PvP mode gameplay
- Repeated hint requests
- AI response consistency
- Engine stability under repeated analysis calls

Particular attention should be given to:
- Shared engine computation paths
- Backend AI subprocess handling
- State synchronization between hint analysis and actual AI turns