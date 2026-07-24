# Kitchen Rush

A fullscreen Pygame kitchen-management game. Start with one hob, one fryer, one drink filler, two storage slots, and a small customer queue. Earn money from completed or partially delivered orders and spend it on upgrades.

## Run

```powershell
python kitchen_rush.py
```

## Current gameplay

- Drag raw burgers, buns, and empty cups from the ingredient bar to stations.
- A short click auto-routes an item: raw ingredients go to their station, buns go to the next burger order, and finished items go to the next matching order. Dragging still gives manual control.
- Burgers must be flipped only when the first side is ready. The second side has its own cooking timer and burn window.
- Potatoes become uncooked chips on the chopping board, then go into the fryer.
- Hold `FILL` on a drink slot. Release between 90% and 100%; above 100% overflows and must be dragged to the BIN.
- With multiple drink slots, activating one fill control fills all occupied unfinished drink slots together.
- Press `P` or click the top-right pause button to freeze the kitchen. Upgrades and save/load are available only while paused.
- Save a run by choosing `SAVE RUN`, typing a name, and pressing Enter. Use `OPEN SAVE` later to load a previous run.
- Drag finished items to the matching order. Extra or incorrect items are rejected.
- A bun must arrive before a burger. Completed orders serve automatically.
- Drag a finished or burnt item into either storage slot or the BIN.
- Waiting tickets are ordered by their remaining preparation work so shorter orders appear first.
- Hold `CHOP` on the chopping board to prepare potatoes, lettuce, or tomatoes.

## Money and upgrades

- Burger: 11c
- Chips: 9c
- Drink: 6c
- Lettuce or tomato: 1c each
- An order that runs out of patience loses 20c, but still pays for items already delivered.
- Chopping board, lettuce, tomato, and potato prep: 50c
- Extra hob: 100c, then 200c, then 300c; maximum 4
- Extra fryer: same pricing and maximum
- Extra drink slot: 125c, then 250c, then 375c; maximum 4

The game uses the supplied image assets and removes connected white/checkered backgrounds when loading them.
