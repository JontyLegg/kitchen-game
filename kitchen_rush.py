import math
import random
import sys
from dataclasses import dataclass, field

import pygame


pygame.init()
pygame.display.set_caption("Kitchen Rush")
SCREEN = pygame.display.set_mode((1180, 760))
CLOCK = pygame.time.Clock()

FONT = pygame.font.SysFont("arial", 20)
SMALL = pygame.font.SysFont("arial", 16)
TITLE = pygame.font.SysFont("arial", 34, bold=True)
BIG = pygame.font.SysFont("arial", 25, bold=True)

BG = (27, 31, 41)
PANEL = (42, 48, 62)
PANEL_DARK = (33, 38, 50)
CREAM = (250, 242, 220)
MUTED = (176, 183, 198)
ORANGE = (244, 143, 53)
RED = (226, 77, 75)
GREEN = (89, 202, 126)
BLUE = (85, 177, 230)
YELLOW = (248, 210, 72)


def draw_text(surface, text, pos, font=FONT, color=CREAM, center=False):
    image = font.render(text, True, color)
    rect = image.get_rect()
    rect.center = pos if center else rect.center
    if not center:
        rect.topleft = pos
    surface.blit(image, rect)


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Order:
    number: int
    items: list
    patience: float = 58.0
    max_patience: float = 58.0
    flash: float = 0.0

    def label(self):
        return " + ".join(self.items)


@dataclass
class Food:
    kind: str
    stage: str = "raw"
    progress: float = 0.0
    flipped: bool = False
    burning: bool = False
    burn_flash: float = 0.0


@dataclass
class Station:
    name: str
    rect: pygame.Rect
    kind: str
    food: Food | None = None
    fill: float = 0.0
    ice: float = 0.0


class KitchenRush:
    def __init__(self):
        self.running = True
        self.score = 0
        self.served = 0
        self.missed = 0
        self.next_order_number = 1
        self.orders: list[Order] = []
        self.message = "Take an order, then use the stations to prepare it."
        self.message_timer = 6.0
        self.spawn_timer = 0.0
        self.selected_order = 0
        self.dragging = None
        self.game_time = 0.0
        self.stations = [
            Station("HOB", pygame.Rect(38, 170, 330, 245), "hob"),
            Station("DEEP FAT FRYER", pygame.Rect(390, 170, 330, 245), "fryer"),
            Station("DRINK FILLER", pygame.Rect(742, 170, 400, 245), "drink"),
        ]
        self.add_order()
        self.add_order()

    def add_order(self):
        # Weighted orders keep the first playthrough learnable but increasingly busy.
        recipes = [["Burger"], ["Chips"], ["Drink"], ["Burger", "Chips"], ["Burger", "Drink"], ["Chips", "Drink"]]
        items = random.choice(recipes)
        self.orders.append(Order(self.next_order_number, items))
        self.next_order_number += 1

    def say(self, message, duration=3.0):
        self.message = message
        self.message_timer = duration

    def selected(self):
        if not self.orders:
            return None
        self.selected_order = clamp(self.selected_order, 0, len(self.orders) - 1)
        return self.orders[self.selected_order]

    def action(self, action):
        order = self.selected()
        if action == "new_order":
            self.add_order()
            self.say("New customer! Select their ticket before cooking.")
            return
        if not order:
            self.say("There are no waiting customers.")
            return
        if action == "start_burger":
            station = self.stations[0]
            if station.food:
                self.say("The hob is already occupied.")
            else:
                station.food = Food("Burger", "raw")
                self.say(f"Patty started for order #{order.number}.")
        elif action == "flip":
            station = self.stations[0]
            if not station.food:
                self.say("Put a patty on the hob first.")
            elif station.food.stage == "ready":
                self.say("That patty is ready — move it to the pass.")
            elif station.food.flipped:
                self.say("You already flipped this patty.")
            else:
                station.food.flipped = True
                station.food.stage = "raw"
                station.food.progress = 0
                self.say("Patty flipped. Keep an eye on the bar!")
        elif action == "start_chips":
            station = self.stations[1]
            if station.food:
                self.say("The fryer is already occupied.")
            else:
                station.food = Food("Chips", "raw")
                self.say("Chips dropped into the fryer.")
        elif action == "start_drink":
            station = self.stations[2]
            if station.food:
                self.say("The drink filler is already occupied.")
            else:
                station.food = Food("Drink", "raw")
                station.fill = 0
                station.ice = 0
                self.say("Cup placed. Add ice, then fill carefully.")
        elif action == "ice":
            station = self.stations[2]
            if station.food and station.food.kind == "Drink":
                station.ice = clamp(station.ice + 0.25, 0, 1)
                self.say("Ice added. The target is one scoop.")
            else:
                self.say("Place a cup at the drink filler first.")
        elif action == "serve":
            self.serve_order(order)
        elif action == "bin":
            for station in self.stations:
                if station.food and station.food.burning:
                    station.food = None
                    station.fill = 0
                    station.ice = 0
                    self.say("Burnt item binned. Start that item again.")
                    return
            self.say("Nothing burnt needs binning.")

    def serve_order(self, order):
        ready = {station.food.kind for station in self.stations if station.food and station.food.stage == "ready"}
        if not set(order.items).issubset(ready):
            self.say("That order is not complete yet — cook every requested item.")
            return
        drink = self.stations[2]
        if "Drink" in order.items and not (0.74 <= drink.ice <= 1.0 and 0.74 <= drink.fill <= 0.96):
            self.say("That drink has the wrong ice or fill amount. Bin it and remake it.")
            return
        for station in self.stations:
            if station.food and station.food.kind in order.items:
                station.food = None
                station.fill = station.ice = 0
        bonus = int(order.patience * 2)
        self.score += 100 + bonus
        self.served += 1
        self.orders.remove(order)
        self.selected_order = max(0, self.selected_order - 1)
        self.say(f"Order #{order.number} served! +{100 + bonus} points.")
        if len(self.orders) < 3:
            self.add_order()

    def update(self, dt):
        self.game_time += dt
        self.message_timer = max(0, self.message_timer - dt)
        if len(self.orders) < 4:
            self.spawn_timer += dt
            if self.spawn_timer > 16:
                self.spawn_timer = 0
                self.add_order()
                self.say("Another customer has arrived.")

        for order in self.orders[:]:
            order.patience -= dt
            if order.patience <= 0:
                self.orders.remove(order)
                self.missed += 1
                self.score = max(0, self.score - 50)
                self.selected_order = max(0, self.selected_order - 1)
                self.say(f"Order #{order.number} walked out. Keep moving!")

        hob = self.stations[0]
        if hob.food and not hob.food.burning:
            speed = 0.32 if not hob.food.flipped else 0.25
            hob.food.progress += dt * speed
            if not hob.food.flipped and hob.food.progress >= 1 and hob.food.burn_flash <= 0:
                hob.food.progress = 1
                hob.food.stage = "warning"
                hob.food.burn_flash = 3
                self.say("FLIP NOW! The patty is starting to burn!", 3)
            elif hob.food.stage == "warning":
                hob.food.burn_flash -= dt
                if hob.food.burn_flash <= 0:
                    hob.food.burning = True
                    self.say("Patty burned! Bin it and start again.")
            elif hob.food.flipped and hob.food.progress >= 1:
                hob.food.progress = 1
                hob.food.stage = "ready"

        fryer = self.stations[1]
        if fryer.food and not fryer.food.burning:
            fryer.food.progress += dt * 0.27
            if fryer.food.progress >= 1 and fryer.food.stage != "warning":
                fryer.food.progress = 1
                fryer.food.stage = "ready"
                fryer.food.burn_flash = 3
                self.say("Chips are ready — take them out before they burn!", 3)
            if fryer.food.stage == "ready" and fryer.food.burn_flash > 0:
                fryer.food.burn_flash -= dt
            elif fryer.food.stage == "ready" and fryer.food.burn_flash <= 0:
                fryer.food.stage = "burned"
                fryer.food.burning = True
                self.say("Chips burned! Bin them and start again.")

        drink = self.stations[2]
        if drink.food and not drink.food.burning:
            if drink.food.stage == "filling" and drink.fill >= 1:
                drink.food.burning = True
                drink.food.burn_flash = 3
                self.say("OVERFILLED! Bin that drink and try again.", 3)

        for station in self.stations:
            if station.food and station.food.stage == "warning":
                station.food.burn_flash = max(0, station.food.burn_flash)

    def draw(self):
        SCREEN.fill(BG)
        draw_text(SCREEN, "KITCHEN RUSH", (38, 22), TITLE, CREAM)
        draw_text(SCREEN, "You are the whole kitchen. Read the tickets, multitask, and serve before patience runs out.", (40, 65), SMALL, MUTED)
        draw_text(SCREEN, f"SCORE  {self.score}", (890, 24), BIG, YELLOW)
        draw_text(SCREEN, f"SERVED {self.served}   WALKED OUT {self.missed}", (890, 58), SMALL, MUTED)
        self.draw_orders()
        for station in self.stations:
            self.draw_station(station)
        self.draw_controls()
        pygame.display.flip()

    def draw_orders(self):
        draw_text(SCREEN, "CUSTOMER TICKETS", (38, 110), BIG, CREAM)
        x = 38
        for index, order in enumerate(self.orders):
            width = 245
            rect = pygame.Rect(x, 440, width, 122)
            selected = index == self.selected_order
            pygame.draw.rect(SCREEN, (67, 75, 95) if selected else PANEL, rect, border_radius=10)
            pygame.draw.rect(SCREEN, ORANGE if selected else (76, 83, 101), rect, 3, border_radius=10)
            draw_text(SCREEN, f"#{order.number}", (x + 14, 451), BIG, ORANGE)
            draw_text(SCREEN, order.label(), (x + 55, 454), FONT, CREAM)
            draw_text(SCREEN, "patience", (x + 14, 493), SMALL, MUTED)
            pygame.draw.rect(SCREEN, PANEL_DARK, (x + 14, 518, width - 28, 12), border_radius=6)
            patience_color = GREEN if order.patience > 25 else RED
            pygame.draw.rect(SCREEN, patience_color, (x + 14, 518, int((width - 28) * order.patience / order.max_patience), 12), border_radius=6)
            x += width + 14
            if x + width > SCREEN.get_width():
                break

    def draw_station(self, station):
        pygame.draw.rect(SCREEN, PANEL, station.rect, border_radius=14)
        pygame.draw.rect(SCREEN, (77, 87, 108), station.rect, 2, border_radius=14)
        draw_text(SCREEN, station.name, (station.rect.x + 18, station.rect.y + 16), BIG, CREAM)
        inner = station.rect.inflate(-36, -70)
        pygame.draw.rect(SCREEN, PANEL_DARK, inner, border_radius=10)
        food = station.food
        if station.kind == "hob":
            pygame.draw.ellipse(SCREEN, (104, 50, 48), inner.inflate(-80, -28))
            if food:
                color = (74, 42, 29) if food.burning else (177, 91, 48)
                pygame.draw.ellipse(SCREEN, color, inner.inflate(-100, -45))
                self.draw_food_status(food, inner, "FLIP" if not food.flipped else "COOKING")
            else:
                draw_text(SCREEN, "Click PREPARE BURGER", inner.center, SMALL, MUTED, True)
        elif station.kind == "fryer":
            pygame.draw.rect(SCREEN, (151, 98, 43), inner.inflate(-55, -28), border_radius=9)
            if food:
                color = (76, 44, 23) if food.burning else (239, 184, 67)
                for i in range(5):
                    pygame.draw.line(SCREEN, color, (inner.centerx - 45 + i * 22, inner.centery - 10), (inner.centerx - 52 + i * 22, inner.centery + 30), 7)
                self.draw_food_status(food, inner, "FRYING")
            else:
                draw_text(SCREEN, "Click DROP CHIPS", inner.center, SMALL, MUTED, True)
        else:
            pygame.draw.rect(SCREEN, (75, 121, 147), inner.inflate(-110, -20), border_radius=12)
            if food:
                pygame.draw.rect(SCREEN, (169, 218, 234), (inner.centerx - 42, inner.centery - 33, 84, 80), border_radius=8)
                if station.fill > 0:
                    pygame.draw.rect(SCREEN, (58, 164, 214), (inner.centerx - 34, inner.centery + 38 - int(64 * station.fill), 68, int(64 * station.fill)), border_radius=4)
                draw_text(SCREEN, f"ICE {int(station.ice * 100)}%", (station.rect.x + 24, station.rect.bottom - 48), SMALL, CREAM)
                draw_text(SCREEN, f"FILL {int(station.fill * 100)}%", (station.rect.x + 120, station.rect.bottom - 48), SMALL, CREAM)
            else:
                draw_text(SCREEN, "Click PREPARE DRINK", inner.center, SMALL, MUTED, True)

    def draw_food_status(self, food, area, label):
        bar = pygame.Rect(area.x + 18, area.bottom - 34, area.width - 36, 14)
        pygame.draw.rect(SCREEN, (24, 27, 35), bar, border_radius=7)
        fill_color = RED if food.burning else (YELLOW if food.progress > 0.8 else ORANGE)
        pygame.draw.rect(SCREEN, fill_color, (bar.x, bar.y, int(bar.width * food.progress), bar.height), border_radius=7)
        text_color = RED if food.burning else (YELLOW if food.stage == "warning" else CREAM)
        status = "BURNING — BIN IT" if food.burning else (f"READY — {food.burn_flash:.1f}s" if food.stage in ("warning", "ready") and food.burn_flash > 0 else label)
        draw_text(SCREEN, status, (area.centerx, area.y + 15), SMALL, text_color, True)
        if food.stage == "warning" or (food.stage == "ready" and food.burn_flash > 0):
            pygame.draw.rect(SCREEN, RED, area, 3, border_radius=10)

    def draw_controls(self):
        pygame.draw.rect(SCREEN, PANEL_DARK, (38, 590, 1104, 138), border_radius=12)
        draw_text(SCREEN, self.message if self.message_timer > 0 else "Select a ticket, then choose the next station action.", (58, 605), FONT, CREAM)
        buttons = [
            ("PREPARE BURGER", pygame.Rect(58, 650, 170, 48), "start_burger"),
            ("FLIP PATTY", pygame.Rect(238, 650, 135, 48), "flip"),
            ("DROP CHIPS", pygame.Rect(383, 650, 135, 48), "start_chips"),
            ("PREPARE DRINK", pygame.Rect(528, 650, 160, 48), "start_drink"),
            ("ADD ICE", pygame.Rect(698, 650, 105, 48), "ice"),
            ("FILL DRINK", pygame.Rect(813, 650, 120, 48), "fill"),
            ("SERVE", pygame.Rect(943, 650, 84, 48), "serve"),
            ("BIN", pygame.Rect(1037, 650, 70, 48), "bin"),
        ]
        for label, rect, action in buttons:
            active = action == "fill" and self.stations[2].food is not None
            pygame.draw.rect(SCREEN, ORANGE if active else (64, 74, 92), rect, border_radius=7)
            pygame.draw.rect(SCREEN, (113, 124, 145), rect, 1, border_radius=7)
            draw_text(SCREEN, label, rect.center, SMALL, BG if active else CREAM, True)

    def click(self, pos):
        for index, order in enumerate(self.orders):
            rect = pygame.Rect(38 + index * 259, 440, 245, 122)
            if rect.collidepoint(pos):
                self.selected_order = index
                self.say(f"Order #{order.number} selected: {order.label()}.")
                return
        buttons = [(pygame.Rect(58, 650, 170, 48), "start_burger"), (pygame.Rect(238, 650, 135, 48), "flip"), (pygame.Rect(383, 650, 135, 48), "start_chips"), (pygame.Rect(528, 650, 160, 48), "start_drink"), (pygame.Rect(698, 650, 105, 48), "ice"), (pygame.Rect(813, 650, 120, 48), "fill"), (pygame.Rect(943, 650, 84, 48), "serve"), (pygame.Rect(1037, 650, 70, 48), "bin")]
        for rect, action in buttons:
            if rect.collidepoint(pos):
                if action == "fill":
                    station = self.stations[2]
                    if station.food and not station.food.burning:
                        station.food.stage = "filling"
                        station.fill = clamp(station.fill + 0.16, 0, 1.15)
                        self.say("Hold FILL to pour. Release before it overflows.")
                    else:
                        self.say("Place a cup at the drink filler first.")
                else:
                    self.action(action)
                return

    def run(self):
        while self.running:
            dt = min(CLOCK.tick(60) / 1000, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_RIGHT:
                        self.selected_order = min(len(self.orders) - 1, self.selected_order + 1)
                    elif event.key == pygame.K_LEFT:
                        self.selected_order = max(0, self.selected_order - 1)
                    elif event.key == pygame.K_SPACE:
                        self.action("serve")
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.click(event.pos)
                    if pygame.Rect(813, 650, 120, 48).collidepoint(event.pos):
                        self.dragging = True
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.dragging = None
                    drink = self.stations[2]
                    if drink.food and drink.food.stage == "filling" and not drink.food.burning and 0.74 <= drink.fill <= 0.96:
                        drink.food.stage = "ready"
                        self.say("Drink ready. Serve it while the ticket is still happy.")

            if self.dragging and pygame.mouse.get_pressed()[0]:
                station = self.stations[2]
                if station.food and not station.food.burning:
                    station.food.stage = "filling"
                    station.fill = clamp(station.fill + dt * 0.7, 0, 1.15)
                    if station.fill >= 1:
                        self.say("OVERFILLING! Release the button!", 1)
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    KitchenRush().run()
