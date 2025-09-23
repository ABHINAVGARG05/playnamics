import math 
import random 
import pygame 
from pygame import mixer 
 
# ============================
# Config & Globals
# ============================
# Screen size constants (feel free to tweak)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Tuning knobs for core mechanics
PLAYER_SPEED = 7             # How fast the player moves left/right
ENEMY_SPEED = 2              # Base horizontal speed of enemies
BULLET_SPEED = 10            # Bullet upward speed
ENEMY_DROP_SPEED = 30        # How much enemies step down when bouncing at edges
MAX_ENEMIES = 8              # Upper limit of enemies on screen
ENEMY_SPAWN_RATE = 120       # Frames between spawns (60 FPS => 2s)
ENEMY_HEALTH_INCREASE_RATE = 3  # Every N levels, enemies gain 1 health

# Obstacle tuning (fast falling hazards)
OBSTACLE_SPAWN_RATE = 90     # Frames between obstacle drops
OBSTACLE_SPEED_MIN = 8
OBSTACLE_SPEED_MAX = 14

# Enemy types (simple enum)
ENEMY_BASIC = 0
ENEMY_FAST = 1
ENEMY_TANK = 2

# Game states (simple state machine)
MENU = 0
PLAYING = 1
GAME_OVER = 2

# ============================
# Pygame Setup & Assets
# ============================
# Initialize the pygame engine (audio, video, fonts, etc.)
pygame.init() 
 
# Create the main window/screen surface
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
 
# Load image assets (must be in the same folder)
background = pygame.image.load('background1.png') 
playerImg = pygame.image.load('player1.png')
enemyImg = pygame.image.load('enemy1.png')
bulletImg = pygame.image.load('bullet1.png') 
icon = pygame.image.load('ufo1.png') 
 
# Audio: background music + sfx
mixer.music.load("background1.wav") 
mixer.music.play(-1)  # Loop forever
laser_sound = mixer.Sound("laser1.wav")
explosion_sound = mixer.Sound("explosion1.wav")
 
# Window metadata
pygame.display.set_caption("Space Invaders Enhanced")
pygame.display.set_icon(icon) 
 
# Fonts used in UI/HUD
font = pygame.font.Font('freesansbold.ttf', 32) 
large_font = pygame.font.Font('freesansbold.ttf', 64)
small_font = pygame.font.Font('freesansbold.ttf', 24)

# Global game state variable to track which screen we're on
game_state = MENU

# ============================
# Game State Container
# ============================ 
class GameState: 
    """Holds all mutable game data. Easy to reset between runs."""
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        # --- Player ---
        self.playerX = SCREEN_WIDTH // 2 - 32  # center horizontally
        self.playerY = SCREEN_HEIGHT - 120     # near bottom
        self.playerX_change = 0                # current horizontal velocity
        self.lives = 3                         # number of hits allowed
        
        # --- Progression ---
        self.score_value = 0
        self.level = 1
        self.game_over = False
        self.difficulty_multiplier = 1.0       # scales enemy speed over time
        
        # --- Enemies ---
        self.enemies = []                      # list of enemy dicts
        self.enemy_spawn_timer = 0
        self.max_enemies_on_screen = 6
        
        # --- Obstacles (fast falling hazards) ---
        self.obstacles = []
        self.obstacle_spawn_timer = 0
        
        # --- Bullets & Power-ups ---
        self.bullets = []                      # list of bullet dicts
        self.shoot_cooldown = 0                # frames left until we can shoot again
        self.max_bullets = 3                   # how many bullets allowed on screen
        self.rapid_fire_timer = 0              # frames remaining for rapid fire
        self.power_ups = []                    # list of power-up dicts
        
        # Start with a few enemies
        self.spawn_initial_enemies()
    
    def spawn_initial_enemies(self):
        """Spawn a few enemies to kick off the action."""
        for _ in range(4):
            self.spawn_enemy()
    
    def spawn_enemy(self):
        """Create one enemy with a type, origin (top/edges), and a fall speed."""
        if len(self.enemies) >= self.max_enemies_on_screen:
            return
        
        # Type selection depends on level
        if self.level >= 5:
            enemy_type = random.choice([ENEMY_BASIC, ENEMY_FAST, ENEMY_TANK])
        elif self.level >= 3:
            enemy_type = random.choice([ENEMY_BASIC, ENEMY_FAST])
        else:
            enemy_type = ENEMY_BASIC
        
        # Base stats per type
        if enemy_type == ENEMY_BASIC:
            health = 1 + (self.level // ENEMY_HEALTH_INCREASE_RATE)
            base_speed = ENEMY_SPEED * self.difficulty_multiplier
            points = 10
        elif enemy_type == ENEMY_FAST:
            health = 1 + (self.level // ENEMY_HEALTH_INCREASE_RATE)
            base_speed = ENEMY_SPEED * self.difficulty_multiplier * 1.8
            points = 20
        else:  # ENEMY_TANK
            health = 3 + (self.level // ENEMY_HEALTH_INCREASE_RATE)
            base_speed = ENEMY_SPEED * self.difficulty_multiplier * 0.6
            points = 30
        
        # Pick spawn side and downward drift amount
        spawn_from = random.choices(["top", "left", "right"], weights=[60, 20, 20], k=1)[0]
        fall_speed = random.uniform(0.4, 1.2) * (1 + 0.1 * (self.level - 1))
        if spawn_from == "top":
            x = random.randint(0, SCREEN_WIDTH - 64)
            y = random.randint(-140, -60)
            x_change = base_speed if random.choice([True, False]) else -base_speed
        elif spawn_from == "left":
            x = -64
            y = random.randint(60, 200)
            x_change = abs(base_speed)
        else:  # right
            x = SCREEN_WIDTH
            y = random.randint(60, 200)
            x_change = -abs(base_speed)
        
        self.enemies.append({
            'x': x,
            'y': y,
            'x_change': x_change,
            'y_change': ENEMY_DROP_SPEED,  # step down when hitting an edge
            'fall_speed': fall_speed,      # continuous downward drift
            'type': enemy_type,
            'health': health,
            'max_health': health,
            'points': points
        })
    
    def spawn_obstacle(self):
        """Create a fast-falling rectangular obstacle from the top."""
        speed = random.randint(OBSTACLE_SPEED_MIN, OBSTACLE_SPEED_MAX) + self.level // 2
        self.obstacles.append({
            'x': random.randint(0, SCREEN_WIDTH - 24),
            'y': -24,
            'w': 20,
            'h': 20,
            'speed': speed,
            'color': (200, 180, 60)
        })

# Single game state instance
game = GameState()

# ============================
# UI Drawing Helpers
# ============================
def draw_text(text, font, color, x, y):
    """Draw text at (x,y). Returns rect for potential alignment logic."""
    text_surface = font.render(text, True, color)
    screen.blit(text_surface, (x, y))
    return text_surface.get_rect(topleft=(x, y))
 
 
def draw_menu():
    """Minimal start screen: title + how to start/quit."""
    screen.fill((0, 0, 0))
    screen.blit(background, (0, 0))
    draw_text("SPACE INVADERS", large_font, (255, 255, 255), SCREEN_WIDTH//2 - 200, 180)
    draw_text("PRESS SPACE TO START", font, (255, 255, 255), SCREEN_WIDTH//2 - 160, 330)
    draw_text("ESC TO QUIT", small_font, (200, 200, 200), SCREEN_WIDTH//2 - 60, 380)


def draw_game_over():
    """Game over UI with score + restart hint."""
    screen.fill((0, 0, 0))
    screen.blit(background, (0, 0))
    draw_text("GAME OVER", large_font, (255, 0, 0), SCREEN_WIDTH//2 - 180, 200)
    draw_text(f"Final Score: {game.score_value}", font, (255, 255, 255), SCREEN_WIDTH//2 - 100, 280)
    draw_text(f"Level Reached: {game.level}", font, (255, 255, 255), SCREEN_WIDTH//2 - 110, 320)
    draw_text("PRESS R TO RESTART", font, (255, 255, 0), SCREEN_WIDTH//2 - 130, 400)
    draw_text("PRESS ESC TO QUIT", font, (255, 255, 255), SCREEN_WIDTH//2 - 120, 450)


def draw_hud():
    """On-screen info during play: score, lives, level, ammo state."""
    draw_text(f"Score: {game.score_value}", font, (255, 255, 255), 10, 10)
    draw_text(f"Lives: {game.lives}", font, (255, 255, 255), 10, 50)
    draw_text(f"Level: {game.level}", font, (255, 255, 255), SCREEN_WIDTH - 150, 10)
    draw_text(f"Enemies: {len(game.enemies)}", small_font, (200, 200, 200), SCREEN_WIDTH - 150, 50)
    
    # Shooting state (cooldown/bullets/rapid fire)
    max_bullets = 5 if game.rapid_fire_timer > 0 else game.max_bullets
    bullets_text = f"Bullets: {len(game.bullets)}/{max_bullets}"
    color = (255, 255, 255) if game.shoot_cooldown == 0 else (255, 100, 100)
    if game.rapid_fire_timer > 0:
        color = (255, 255, 0)
    draw_text(bullets_text, small_font, color, SCREEN_WIDTH - 150, 75)
    if game.rapid_fire_timer > 0:
        seconds_left = game.rapid_fire_timer // 60
        draw_text(f"RAPID FIRE: {seconds_left}s", small_font, (255, 255, 0), SCREEN_WIDTH - 150, 95)
    
    # Level progress hint
    points_needed = 150 + (game.level * 50)
    next_level_score = points_needed * game.level
    if game.score_value < next_level_score:
        progress = game.score_value % points_needed
        draw_text(f"Next Level: {progress}/{points_needed}", small_font, (255, 255, 0), 10, 90)
 
 
def draw_player():
    """Render player sprite at current position."""
    screen.blit(playerImg, (game.playerX, game.playerY))
 

def draw_enemy(enemy):
    """Render enemy with tint and health bar when needed."""
    enemy_surface = enemyImg.copy()
    if enemy['type'] == ENEMY_FAST:
        enemy_surface.fill((255, 100, 100), special_flags=pygame.BLEND_ADD)
    elif enemy['type'] == ENEMY_TANK:
        enemy_surface.fill((100, 255, 100), special_flags=pygame.BLEND_ADD)
    screen.blit(enemy_surface, (enemy['x'], enemy['y']))
    if enemy['max_health'] > 1:
        bar_width, bar_height = 40, 4
        bar_x, bar_y = enemy['x'] + 12, enemy['y'] - 8
        pygame.draw.rect(screen, (255, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        health_width = int((enemy['health'] / enemy['max_health']) * bar_width)
        if health_width > 0:
            pygame.draw.rect(screen, (0, 255, 0), (bar_x, bar_y, health_width, bar_height))


def draw_bullet(x, y):
    """Render a bullet. Sprite is offset to look centered from the ship."""
    screen.blit(bulletImg, (x + 16, y + 10)) 
 
 
def draw_power_up(power_up):
    """Render a star-shaped rapid fire power-up (simple shape)."""
    if power_up['type'] == 'rapid_fire':
        points = []
        center_x, center_y = power_up['x'] + 16, power_up['y'] + 16
        for i in range(8):
            angle = i * math.pi / 4
            radius = 12 if i % 2 == 0 else 6
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append((x, y))
        pygame.draw.polygon(screen, (255, 255, 0), points)


# ============================
# Core Mechanics
# ============================

def is_collision(x1, y1, x2, y2, threshold=27):
    """Distance-based circular collision check."""
    distance = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    return distance < threshold


def update_player():
    """Move player horizontally and clamp to screen bounds."""
    game.playerX += game.playerX_change
    if game.playerX <= 0:
        game.playerX = 0
    elif game.playerX >= SCREEN_WIDTH - 64:
        game.playerX = SCREEN_WIDTH - 64


def create_bullet():
    """Shoot a bullet if cooldown allows (faster during rapid fire)."""
    cooldown = 5 if game.rapid_fire_timer > 0 else 15
    max_bullets = 5 if game.rapid_fire_timer > 0 else game.max_bullets
    if game.shoot_cooldown <= 0 and len(game.bullets) < max_bullets:
        game.bullets.append({'x': game.playerX, 'y': game.playerY, 'speed': BULLET_SPEED})
        laser_sound.play()
        game.shoot_cooldown = cooldown


def update_bullets():
    """Move bullets up, manage cooldown and power-up timers, cull off-screen."""
    if game.shoot_cooldown > 0:
        game.shoot_cooldown -= 1
    if game.rapid_fire_timer > 0:
        game.rapid_fire_timer -= 1
    for bullet in game.bullets[:]:
        bullet['y'] -= bullet['speed']
        if bullet['y'] < 0:
            game.bullets.remove(bullet)


def update_power_ups():
    """Drop power-ups and grant effects on pickup."""
    for power_up in game.power_ups[:]:
        power_up['y'] += power_up.get('speed', 2)
        if power_up['y'] > SCREEN_HEIGHT:
            game.power_ups.remove(power_up)
            continue
        if is_collision(power_up['x'], power_up['y'], game.playerX, game.playerY, 40):
            if power_up['type'] == 'rapid_fire':
                game.rapid_fire_timer = 300  # 5s at 60 FPS
            game.power_ups.remove(power_up)
            laser_sound.play()


def update_enemies():
    """Spawn enemies over time, move them, and process bullet collisions."""
    global game_state
    # Timed spawns (faster with level)
    game.enemy_spawn_timer += 1
    spawn_rate = max(30, ENEMY_SPAWN_RATE - (game.level * 10))
    if game.enemy_spawn_timer >= spawn_rate:
        game.spawn_enemy()
        game.enemy_spawn_timer = 0
    # Move and resolve collisions
    for enemy in game.enemies[:]:
        if enemy['y'] > SCREEN_HEIGHT - 160:  # reached player zone
            game.lives -= 1
            game.enemies.remove(enemy)
            if game.lives <= 0:
                game.game_over = True
                game_state = GAME_OVER
            continue
        enemy['x'] += enemy['x_change']
        # bounce at edges and step down
        if enemy['x'] <= 0:
            enemy['x_change'] = abs(enemy['x_change'])
            enemy['y'] += enemy['y_change']
        elif enemy['x'] >= SCREEN_WIDTH - 64:
            enemy['x_change'] = -abs(enemy['x_change'])
            enemy['y'] += enemy['y_change']
        # slow downward drift per enemy
        enemy['y'] += enemy.get('fall_speed', 0.5)
        # bullet collisions
        for bullet in game.bullets[:]:
            if is_collision(enemy['x'], enemy['y'], bullet['x'], bullet['y']):
                game.bullets.remove(bullet)
                enemy['health'] -= 1
                if enemy['health'] <= 0:
                    explosion_sound.play()
                    game.score_value += enemy['points']
                    game.enemies.remove(enemy)
                    # 15% chance of a rapid-fire power-up
                    if random.random() < 0.15:
                        game.power_ups.append({'x': enemy['x'], 'y': enemy['y'], 'type': 'rapid_fire', 'speed': 2})
                    # level up when enough points collected (harder with level)
                    points_needed = 150 + (game.level * 50)
                    if game.score_value >= points_needed * game.level:
                        game.level += 1
                        game.difficulty_multiplier += 0.2
                        game.max_enemies_on_screen = min(MAX_ENEMIES, 4 + game.level)
                        print(f"Level {game.level}! Difficulty increased!")
                break


def rect_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    """Axis-aligned rectangle overlap test (fast)."""
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)


def update_obstacles():
    """Spawn, move, and handle obstacle collisions with bullets and player."""
    global game_state
    game.obstacle_spawn_timer += 1
    rate = max(30, OBSTACLE_SPAWN_RATE - game.level * 5)
    if game.obstacle_spawn_timer >= rate:
        game.spawn_obstacle()
        game.obstacle_spawn_timer = 0
    player_rect = (game.playerX, game.playerY, 64, 64)
    for obs in game.obstacles[:]:
        obs['y'] += obs['speed']
        if obs['y'] > SCREEN_HEIGHT:
            game.obstacles.remove(obs)
            continue
        # bullets are absorbed by obstacles
        for bullet in game.bullets[:]:
            if rect_overlap(bullet['x'], bullet['y'], 8, 16, obs['x'], obs['y'], obs['w'], obs['h']):
                game.bullets.remove(bullet)
                break
        # player takes damage
        if rect_overlap(player_rect[0], player_rect[1], player_rect[2], player_rect[3], obs['x'], obs['y'], obs['w'], obs['h']):
            game.lives -= 1
            game.obstacles.remove(obs)
            if game.lives <= 0:
                game.game_over = True
                # Transition to GAME_OVER state so the loop shows the Game Over screen
                game_state = GAME_OVER


def draw_obstacle(obs):
    """Simple rectangle style for obstacles (could be replaced with sprites)."""
    rect = pygame.Rect(int(obs['x']), int(obs['y']), obs['w'], obs['h'])
    pygame.draw.rect(screen, obs['color'], rect)
    pygame.draw.rect(screen, (80, 70, 30), rect, 2)


# ============================
# Input Handling
# ============================

def handle_menu_input():
    """Handle menu keys: SPACE to start, ESC to quit."""
    global game_state
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                game.reset_game()
                game_state = PLAYING
            elif event.key == pygame.K_ESCAPE:
                return False
    return True


def handle_game_input():
    """In-game input: left/right movement, shoot with space, ESC back to menu."""
    global game_state
    keys = pygame.key.get_pressed()
    for event in pygame.event.get(): 
        if event.type == pygame.QUIT: 
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                create_bullet()
            elif event.key == pygame.K_ESCAPE:
                game_state = MENU
    # continuous movement
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        game.playerX_change = -PLAYER_SPEED
    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        game.playerX_change = PLAYER_SPEED
    else:
        game.playerX_change = 0
    return True


def handle_game_over_input():
    """Game over input: R to restart, ESC to quit."""
    global game_state
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                game.reset_game()
                game_state = PLAYING
            elif event.key == pygame.K_ESCAPE:
                return False
    return True


# ============================
# Main Loop
# ============================

def main():
    """Central game loop controlling all screens and updates at ~60 FPS."""
    global game_state
    clock = pygame.time.Clock()
    running = True
    while running:
        clock.tick(60)  # target 60 FPS
        if game_state == MENU:
            running = handle_menu_input()
            draw_menu()
        elif game_state == PLAYING:
            running = handle_game_input()
            if not game.game_over:
                update_player()
                update_bullets()
                update_power_ups()
                update_enemies()
                update_obstacles()
            # Render order: background -> world -> UI
            screen.fill((0, 0, 0))
            screen.blit(background, (0, 0))
            draw_player()
            for enemy in game.enemies:
                draw_enemy(enemy)
            for bullet in game.bullets:
                draw_bullet(bullet['x'], bullet['y'])
            for power_up in game.power_ups:
                draw_power_up(power_up)
            for obs in game.obstacles:
                draw_obstacle(obs)
            draw_hud()
        elif game_state == GAME_OVER:
            running = handle_game_over_input()
            draw_game_over()
        pygame.display.update()
    pygame.quit()

 
if __name__ == "__main__":
    main()