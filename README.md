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
- Click and hold `FILL DRINK` until it completes; filling takes longer than the other stations and then changes the empty cup into a filled drink.
- Drag a bun onto an order before dragging a burger onto it.
- Drag each finished item onto its matching customer ticket in any order. Ticket outlines are red for untouched, orange for partly complete, and green when complete.
- Completed tickets are served automatically as soon as all requested items arrive.
- Click `BIN` when an item has burned or a drink has been spoiled.
- Left/right arrow keys change the selected ticket; Space serves the selected ticket; Escape quits.

The queue is intentionally manageable at the start, then adds customers over time. There is one of each appliance and no toppings yet.
