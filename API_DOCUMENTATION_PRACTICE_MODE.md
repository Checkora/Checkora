# Practice Mode API Documentation

## Overview
This document outlines the API changes and new endpoints added for the Practice Mode feature.

## Existing Endpoints Updated

### `/api/new-game/` (POST)
**Changes**: Added support for `'practice'` mode

**Request Body**:
```json
{
  "mode": "practice",
  "difficulty": "medium",
  "player_color": "white",
  "white_name": "Player Name",
  "black_name": "AI"
}
```

**Response**: Same as before, with `mode: "practice"` in response

**Behavior**:
- Creates a practice game without ranking implications
- Sets `is_practice` flag in session
- Game results will NOT be recorded

---

### `/api/ai-move/` (POST)
**Changes**: Now works with both 'ai' and 'practice' modes

**Validation**:
```python
if game.mode not in ('ai', 'practice'):
    # Returns error
```

**Behavior**:
- Works identically for both modes
- Results only recorded for 'ai' mode
- Practice mode moves do NOT update rankings

**Example Request**:
```json
{}
```

**Example Response**:
```json
{
  "valid": true,
  "ai_move": {
    "from_row": 6,
    "from_col": 4,
    "to_row": 4,
    "to_col": 4
  },
  "board": [...],
  "current_turn": "white",
  "game_status": "active"
}
```

---

### `/api/move/` (POST)
**Changes**: No changes, works seamlessly with practice mode

**Behavior**:
- Game results NOT recorded for practice mode moves
- All move validation identical to other modes

---

### `/api/resign/`, `/api/draw/` (POST)
**Changes**: No changes, handle practice mode correctly

**Behavior**:
- Game results NOT recorded for practice mode
- Resignation/draw handling identical to other modes

---

## New Endpoints

### `/api/suggestion/` (GET)
**Purpose**: Get AI-recommended move for educational purposes without playing it

**Request**:
```
GET /api/suggestion/
```

**Query Parameters**: None

**Response (Success)**:
```json
{
  "valid": true,
  "move": {
    "from_row": 6,
    "from_col": 4,
    "to_row": 4,
    "to_col": 4
  },
  "move_notation": "e2 → e4",
  "message": "Suggested move: e2 → e4"
}
```

**Response (No Active Game)**:
```json
{
  "valid": false,
  "message": "No active game."
}
```

**Response (Wrong Mode)**:
```json
{
  "valid": false,
  "message": "Suggestions not available in this mode."
}
```

**Response (No Legal Moves)**:
```json
{
  "valid": false,
  "message": "No legal moves available."
}
```

**Features**:
- Works in both 'practice' and 'ai' modes
- Does NOT make the move, only returns it
- Uses same difficulty-based depth as ai-move
- Respects session difficulty setting
- Returns move in algebraic notation (e.g., "e2 → e4")
- Educational use only

**Implementation Details**:
- Uses existing `ChessGame.get_ai_move(depth)` method
- Retrieves difficulty from session: `request.session.get('difficulty', 'medium')`
- Depth mapping: Easy=2, Medium=3, Hard=5
- No game state is modified

---

## Data Flow Diagrams

### Starting a Practice Game
```
User clicks "Practice vs AI"
    ↓
POST /api/new-game/ (mode: 'practice')
    ↓
Game created with is_practice = True
    ↓
Session stores is_practice flag
    ↓
Game loads with suggestion panel visible
```

### Getting Suggestions
```
Player makes move
    ↓
POST /api/move/
    ↓
Move validated and board updated
    ↓
GET /api/suggestion/ 
    ↓
AI calculates best move (doesn't play it)
    ↓
Move returned in notation format
    ↓
Suggestion panel updated in UI
```

### AI's Turn in Practice
```
POST /api/ai-move/
    ↓
AI move made on board
    ↓
GET /api/suggestion/ 
    ↓
Suggestion for next player move generated
    ↓
Suggestion panel shows recommended move
```

### Ending Practice Game
```
Game ends (checkmate/stalemate/resignation/draw)
    ↓
record_game_result(mode='practice', ...)
    ↓
Function detects practice mode
    ↓
No database entry created
    ↓
User stats remain unchanged
```

---

## Session Variables

### New Session Variables
- `is_practice`: Boolean flag indicating practice mode (set by new_game endpoint)

### Existing Session Variables Used
- `game`: Game state dict
- `difficulty`: AI difficulty level
- `player_color`: Player's color
- `white_name`: Player's name
- `black_name`: 'AI' for practice mode

---

## Error Handling

### Practice Mode Specific Errors
None new - practice mode handles errors identically to ai mode

### Suggestion Endpoint Errors
1. **No Active Game**: Returns 400 with "No active game"
2. **Wrong Mode**: Returns 400 with "Suggestions not available"
3. **No Legal Moves**: Returns valid=False with "No legal moves available"
4. **Engine Failure**: Returns valid=False (caught gracefully)

---

## Performance Considerations

### Suggestion Requests
- Uses same engine as AI moves (CPU bound)
- Should be called sparingly (every player move, not continuously)
- Frontend implements smart calling to avoid spam

### Database
- No extra database writes for practice mode
- Reduces GameResult table bloat
- Better performance for stats queries (fewer records to scan)

---

## Testing Examples

### cURL Examples

**Start Practice Game**:
```bash
curl -X POST http://localhost:8000/play/api/new-game/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: YOUR_CSRF_TOKEN" \
  -d '{
    "mode": "practice",
    "difficulty": "medium",
    "player_color": "white",
    "white_name": "TestPlayer",
    "black_name": "AI"
  }'
```

**Get Suggestion**:
```bash
curl -X GET http://localhost:8000/play/api/suggestion/ \
  -H "X-CSRFToken: YOUR_CSRF_TOKEN"
```

**Make AI Move in Practice**:
```bash
curl -X POST http://localhost:8000/play/api/ai-move/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: YOUR_CSRF_TOKEN" \
  -d '{}'
```

---

## Backward Compatibility

✅ All existing endpoints remain fully compatible
✅ No breaking changes to existing mode handling
✅ 'pvp' and 'ai' modes work exactly as before
✅ Practice mode is opt-in feature
✅ Old clients continue to work without modification

---

## Frontend Integration

### JavaScript Functions
```javascript
// Request a suggestion (get AI recommendation)
async function requestSuggestion()

// Clear the suggestion display
function clearSuggestion()

// Check if suggestions enabled
suggestionsEnabled // boolean

// Check if practice mode active
isPracticeMode // boolean
```

### Example Usage
```javascript
// After player moves in practice mode
if (isPracticeMode && suggestionsEnabled) {
  setTimeout(requestSuggestion, 300);
}

// Response from /api/suggestion/
{
  valid: true,
  move_notation: "e2 → e4",  // Display this
  move: {...}                 // Internal use
}
```

---

## Future API Extensions

Possible future endpoints:
- `/api/practice-stats/` - Get practice mode statistics
- `/api/practice-hint/` - Get verbal hint instead of move
- `/api/practice-analysis/` - Get move analysis
- `/api/practice-tutorial/` - Get tutorial for position

---

## Questions & Troubleshooting

**Q: Why does suggestion fail with "wrong mode"?**
A: Ensure game was started with `mode: "practice"` not `mode: "ai"`

**Q: Suggestions don't update after AI moves?**
A: Check that `isPracticeMode` is true and suggestion panel is visible

**Q: Why aren't practice games counted in stats?**
A: By design - practice mode doesn't affect rankings/stats. Check `record_game_result()` logic

**Q: Can I use suggestions in ranked AI mode?**
A: Yes, the endpoint works in both modes, but typically used in practice mode only

