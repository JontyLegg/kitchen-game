# Kitchen Rush

A small Pygame time-management game where one chef handles burgers, chips, and drinks for a growing queue of customers.

## Run

```powershell
python kitchen_rush.py
```

## How to play

- Click a customer ticket to select it.
- Use `PREPARE BURGER`, then click `FLIP PATTY` before the hob bar finishes flashing.
- Use `DROP CHIPS`; remove them during their three-second ready window.
- Use `PREPARE DRINK`, add one scoop of ice, then hold `FILL DRINK` and release around 80% full.
- Click `SERVE` when all requested items are ready.
- Click `BIN` when an item has burned or a drink has been spoiled.
- Left/right arrow keys change the selected ticket; Space serves the selected ticket; Escape quits.

The queue is intentionally manageable at the start, then adds customers over time. There is one of each appliance and no toppings yet.
