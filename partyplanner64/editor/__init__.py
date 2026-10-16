"""The editor's state: boards, undo history and the event library.

- board_state.py: the board state and its reducers (boardState.ts);
- history.py: the undo history (store.ts's redux-undo configuration);
- store.py: the store singleton (`store`), the event library's home;
- boards.py: the app's board functions (boards.ts);
- events/: the event library implementation the editor uses;
- ops.py: API ops made ready for the reducers;
- images.py: the image cache (data URLs <-> /api/image/<sha1>);
- jsjson.py: JSON as JavaScript writes it.
"""
