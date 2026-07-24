# Kitchen Rush

A fullscreen Pygame kitchen-management game. Start with one hob, one fryer, one drink filler, two storage slots, and a small customer queue. Earn money from completed or partially delivered orders and spend it on upgrades.

## Run

```powershell
python kitchen_rush.py
```

## Current gameplay

- Drag raw burgers, buns, and empty cups from the ingredient bar to stations.
- Burgers must be flipped only when the first side is ready. The second side has its own cooking timer and burn window.
- Potatoes become uncooked chips on the chopping board, then go into the fryer.
- Hold `FILL` on a drink slot. Release between 90% and 100%; above 100% overflows and must be dragged to the BIN.
- Drag finished items to the matching order. Extra or incorrect items are rejected.
- A bun must arrive before a burger. Completed orders serve automatically.
- Drag a finished or burnt item into either storage slot or the BIN.
- Hold `CHOP` on the chopping board to prepare potatoes, lettuce, or tomatoes.

## Money and upgrades

- Burger: 15c
- Chips: 13c
- Drink: 10c
- Lettuce or tomato: 5c each
- An order that runs out of patience loses 10c, but still pays for items already delivered.
- Chopping board, lettuce, tomato, and potato prep: 50c
- Extra hob: 100c, then 200c, then 300c; maximum 4
- Extra fryer: same pricing and maximum
- Extra drink slot: 125c, then 250c, then 375c; maximum 4

The game uses the supplied image assets and removes connected white/checkered backgrounds when loading them.
