# Kitchen Rush

A small Pygame time-management game where one chef handles burgers, chips, and drinks for a growing queue of customers.

## Run

```powershell
python kitchen_rush.py
```

## How to play

- Click a customer ticket to select it.
- Drag the ingredient cards onto the correct cooker: burger to the hob, chips to the fryer, and drink to the filler.
- Tap the burger on the hob to flip it. Tap a ready cooker to pick the finished item up, then drag it to `PLATE UP`.
- Click and hold `FILL DRINK`, then release around 80% full. The drink changes from an empty cup to a filled drink when complete.
- Drag a bun onto every plate before dragging a burger onto it.
- Click `SERVE` when the selected ticket's plate is complete.
- Click `BIN` when an item has burned or a drink has been spoiled.
- Left/right arrow keys change the selected ticket; Space serves the selected ticket; Escape quits.

The queue is intentionally manageable at the start, then adds customers over time. There is one of each appliance and no toppings yet.
