import pygame
import sys
import random
import cv2
import mediapipe as mp
import time

# ============================================================
#                  GESTURE DETECTION SETUP
# ============================================================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)

def get_finger_status(hand_landmarks):
    landmarks = hand_landmarks.landmark
    fingers = []
    if landmarks[4].x < landmarks[3].x:
        fingers.append(1)
    else:
        fingers.append(0)
    tips = [8, 12, 16, 20]
    bases = [6, 10, 14, 18]
    for tip, base in zip(tips, bases):
        fingers.append(1 if landmarks[tip].y < landmarks[base].y else 0)
    return fingers

def classify_gesture(fingers):
    if fingers == [1, 1, 1, 1, 1]:
        return "open_palm"
    elif fingers == [0, 0, 0, 0, 0]:
        return "fist"
    elif fingers == [0, 1, 1, 0, 0]:
        return "victory"
    elif fingers == [1, 0, 0, 0, 0]:
        return "thumb_up"
    else:
        return "unknown"

prev_wrist_x = None
prev_time = None
SWIPE_THRESHOLD = 0.035
SWIPE_TIME_WINDOW = 0.5

current_gesture = "unknown"
swipe_left_trigger = False
swipe_right_trigger = False


def process_webcam_gestures():
    """Reads one webcam frame, updates current_gesture and swipe triggers.
    Returns the annotated frame for the small preview window (or None)."""
    global prev_wrist_x, prev_time, current_gesture, swipe_left_trigger, swipe_right_trigger

    swipe_left_trigger = False
    swipe_right_trigger = False

    success, frame = cap.read()
    if not success:
        return None

    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    current_gesture = "unknown"
    current_time = time.time()

    if results.multi_hand_landmarks and results.multi_handedness:
        for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
            hand_label = handedness.classification[0].label

            mp.solutions.drawing_utils.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            if hand_label == "Right":
                fingers = get_finger_status(hand_landmarks)
                current_gesture = classify_gesture(fingers)

                wrist_x = hand_landmarks.landmark[0].x
                if prev_wrist_x is not None and prev_time is not None:
                    dx = wrist_x - prev_wrist_x
                    dt = current_time - prev_time
                    if 0 < dt < SWIPE_TIME_WINDOW:
                        if dx > SWIPE_THRESHOLD:
                            swipe_right_trigger = True
                        elif dx < -SWIPE_THRESHOLD:
                            swipe_left_trigger = True
                prev_wrist_x = wrist_x
                prev_time = current_time

    cv2.putText(frame, f"Gesture: {current_gesture}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if swipe_left_trigger:
        cv2.putText(frame, "SWIPE LEFT!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
    if swipe_right_trigger:
        cv2.putText(frame, "SWIPE RIGHT!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 0), 2)
    return frame


# ============================================================
#                       PYGAME SETUP
# ============================================================
pygame.init()

WIDTH, HEIGHT = 1000, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AI Gesture Adventure")
clock = pygame.time.Clock()

enemy_img = pygame.image.load("assets/enemy_idle.png").convert_alpha()
enemy_defeated_img = pygame.image.load("assets/enemy_defeated.png").convert_alpha()
enemy_img = pygame.transform.scale(enemy_img, (45, 45))
enemy_defeated_img = pygame.transform.scale(enemy_defeated_img, (45, 45))

SKY_TOP = (100, 180, 255)
SKY_BOTTOM = (200, 230, 255)
HILL_COLOR = (80, 160, 90)
GROUND_COLOR = (60, 40, 30)
GROUND_TOP = (90, 60, 40)
HERO_BODY = (220, 60, 60)
HERO_HEAD = (255, 210, 160)
OBSTACLE_COLOR = (90, 90, 90)
BEAM_COLOR = (140, 60, 40)
COIN_COLOR = (255, 215, 0)
DASH_TRAIL_COLOR = (255, 255, 150)

GROUND_Y = HEIGHT - 80

hero_width = 40
HERO_NORMAL_HEIGHT = 60
HERO_SLIDE_HEIGHT = 30
hero_height = HERO_NORMAL_HEIGHT
hero_x = 120
hero_y = GROUND_Y - hero_height
hero_vel_y = 0
JUMP_STRENGTH = -17
GRAVITY = 0.8
is_jumping = False
run_frame = 0

is_sliding = False
slide_timer = 0
SLIDE_DURATION = 50

is_dashing = False
dash_timer = 0
DASH_DURATION = 30

hill_scroll = 0
ground_scroll = 0
GAME_SPEED = 5

obstacles = []
coins = []
enemies = []
spawn_timer = 0
score = 0
game_over = False
attack_flash_timer = 0

was_open_palm = False  # for edge-detecting jump trigger


def draw_gradient_sky():
    for y in range(HEIGHT - 80):
        ratio = y / (HEIGHT - 80)
        r = SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio
        g = SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio
        b = SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio
        pygame.draw.line(screen, (r, g, b), (0, y), (WIDTH, y))


def draw_hills(scroll):
    for i in range(-1, 3):
        x = i * 300 - (scroll % 300)
        pygame.draw.ellipse(screen, HILL_COLOR, (x, GROUND_Y - 60, 350, 120))


def draw_ground(scroll):
    pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
    pygame.draw.rect(screen, GROUND_TOP, (0, GROUND_Y, WIDTH, 10))
    for i in range(-1, WIDTH // 40 + 2):
        x = i * 40 - (scroll % 40)
        pygame.draw.line(screen, (40, 25, 15), (x, GROUND_Y + 10), (x, HEIGHT), 2)


def draw_hero(x, y, h, frame, dashing):
    if dashing:
        for i in range(1, 4):
            trail_x = x - i * 14
            s = pygame.Surface((hero_width, h), pygame.SRCALPHA)
            s.fill((*DASH_TRAIL_COLOR, max(0, 90 - i * 25)))
            screen.blit(s, (trail_x, y))

    leg_offset = 8 if frame % 20 < 10 else -8
    body_h = max(10, h - 20)
    pygame.draw.rect(screen, HERO_BODY, (x, y + (h - body_h), hero_width, body_h - 10))
    pygame.draw.circle(screen, HERO_HEAD, (x + hero_width // 2, y + 12), 14 if h == HERO_NORMAL_HEIGHT else 12)
    if h == HERO_NORMAL_HEIGHT:
        pygame.draw.line(screen, HERO_BODY, (x + 10, y + h - 10),
                          (x + 10 + leg_offset, y + h + 10), 6)
        pygame.draw.line(screen, HERO_BODY, (x + hero_width - 10, y + h - 10),
                          (x + hero_width - 10 - leg_offset, y + h + 10), 6)


def hero_rect():
    return pygame.Rect(hero_x, hero_y, hero_width, hero_height)


def spawn_obstacle():
    obstacles.append({"x": WIDTH + 50, "y": GROUND_Y - 40, "w": 30, "h": 40, "type": "ground"})


def spawn_beam():
    beam_y = GROUND_Y - 70
    obstacles.append({"x": WIDTH + 50, "y": beam_y, "w": 60, "h": 22, "type": "beam"})


def spawn_coin():
    coins.append({"x": WIDTH + 50, "y": GROUND_Y - 120, "r": 12})


def spawn_enemy():
    enemies.append({"x": WIDTH + 50, "y": GROUND_Y - 45, "w": 45, "h": 45, "alive": True})


font = pygame.font.SysFont(None, 32)

running = True
while running:
    # ---- Webcam gesture read (once per game frame) ----
    cam_frame = process_webcam_gestures()
    if cam_frame is not None:
        small = cv2.resize(cam_frame, (240, 180))
        cv2.imshow("Gesture Camera", small)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        running = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and game_over:
                obstacles.clear()
                coins.clear()
                enemies.clear()
                hero_height = HERO_NORMAL_HEIGHT
                hero_y = GROUND_Y - hero_height
                hero_vel_y = 0
                is_jumping = False
                is_sliding = False
                is_dashing = False
                score = 0
                game_over = False
            if not game_over:
                if event.key == pygame.K_LEFT and not is_jumping and not is_sliding:
                    is_sliding = True
                    slide_timer = SLIDE_DURATION
                if event.key == pygame.K_RIGHT and not is_dashing:
                    is_dashing = True
                    dash_timer = DASH_DURATION

    # ---- Gesture-triggered actions ----
    if not game_over:
        # Jump: Open Palm (edge-triggered so it doesn't spam-jump while held)
        is_open_palm_now = (current_gesture == "open_palm")
        if is_open_palm_now and not was_open_palm and not is_jumping and not is_sliding:
            hero_vel_y = JUMP_STRENGTH
            is_jumping = True
        was_open_palm = is_open_palm_now

        # Slide: Swipe Left
        if swipe_left_trigger and not is_jumping and not is_sliding:
            is_sliding = True
            slide_timer = SLIDE_DURATION

        # Dash: Swipe Right
        if swipe_right_trigger and not is_dashing:
            is_dashing = True
            dash_timer = DASH_DURATION

    if not game_over:
        keys = pygame.key.get_pressed()

        # Keyboard fallback for jump
        if keys[pygame.K_SPACE] and not is_jumping and not is_sliding:
            hero_vel_y = JUMP_STRENGTH
            is_jumping = True

        hero_vel_y += GRAVITY
        hero_y += hero_vel_y

        if is_sliding:
            hero_height = HERO_SLIDE_HEIGHT
            slide_timer -= 1
            if slide_timer <= 0:
                is_sliding = False
        else:
            hero_height = HERO_NORMAL_HEIGHT

        if hero_y >= GROUND_Y - hero_height:
            hero_y = GROUND_Y - hero_height
            hero_vel_y = 0
            is_jumping = False

        if is_dashing:
            dash_timer -= 1
            if dash_timer <= 0:
                is_dashing = False

        hill_scroll += GAME_SPEED // 2
        ground_scroll += GAME_SPEED
        run_frame += 1

        spawn_timer += 1
        if spawn_timer > 90:
            choice = random.random()
            if choice < 0.3:
                spawn_obstacle()
            elif choice < 0.55:
                spawn_coin()
            elif choice < 0.8:
                spawn_enemy()
            else:
                spawn_beam()
            spawn_timer = 0

        for obs in obstacles:
            obs["x"] -= GAME_SPEED
        for c in coins:
            c["x"] -= GAME_SPEED
        for e in enemies:
            e["x"] -= GAME_SPEED

        obstacles = [o for o in obstacles if o["x"] > -70]
        coins = [c for c in coins if c["x"] > -50]
        enemies = [e for e in enemies if e["x"] > -50]

        h_rect = hero_rect()

        if not is_dashing:
            for obs in obstacles:
                obs_rect = pygame.Rect(obs["x"], obs["y"], obs["w"], obs["h"])
                if h_rect.colliderect(obs_rect):
                    game_over = True

        remaining_coins = []
        for c in coins:
            coin_rect = pygame.Rect(c["x"] - c["r"], c["y"] - c["r"], c["r"] * 2, c["r"] * 2)
            if h_rect.colliderect(coin_rect):
                score += 10
            else:
                remaining_coins.append(c)
        coins = remaining_coins

        # Attack: Fist gesture OR 'F' key fallback
        attack_pressed = keys[pygame.K_f] or (current_gesture == "fist")

        for e in enemies:
            if not e["alive"]:
                continue
            enemy_rect = pygame.Rect(e["x"], e["y"], e["w"], e["h"])
            if h_rect.colliderect(enemy_rect.inflate(15, 15)):
                if is_dashing or attack_pressed:
                    e["alive"] = False
                    score += 20
                    attack_flash_timer = 10
                else:
                    game_over = True

        if attack_flash_timer > 0:
            attack_flash_timer -= 1

    # ==================== Draw everything ====================
    draw_gradient_sky()
    draw_hills(hill_scroll)
    draw_ground(ground_scroll)

    for obs in obstacles:
        color = BEAM_COLOR if obs["type"] == "beam" else OBSTACLE_COLOR
        pygame.draw.rect(screen, color, (obs["x"], obs["y"], obs["w"], obs["h"]))
        if obs["type"] == "beam":
            pygame.draw.rect(screen, (80, 40, 25), (obs["x"] + 5, obs["y"] + obs["h"], 6, 20))
            pygame.draw.rect(screen, (80, 40, 25), (obs["x"] + obs["w"] - 11, obs["y"] + obs["h"], 6, 20))

    for c in coins:
        pygame.draw.circle(screen, COIN_COLOR, (c["x"], c["y"]), c["r"])

    for e in enemies:
        img = enemy_img if e["alive"] else enemy_defeated_img
        screen.blit(img, (e["x"], e["y"]))

    if attack_flash_timer > 0:
        pygame.draw.rect(screen, (255, 255, 0), (0, 0, WIDTH, HEIGHT), 8)

    draw_hero(hero_x, hero_y, hero_height, run_frame if not is_jumping else 0, is_dashing)

    score_label = font.render(f"Score: {score}", True, (30, 30, 30))
    screen.blit(score_label, (10, 10))

    gesture_label = font.render(f"Gesture: {current_gesture}", True, (30, 30, 30))
    screen.blit(gesture_label, (10, 45))

    if is_dashing:
        dash_label = font.render("DASH!", True, (255, 140, 0))
        screen.blit(dash_label, (10, 75))
    if is_sliding:
        slide_label = font.render("SLIDE!", True, (0, 100, 200))
        screen.blit(slide_label, (10, 75))

    if game_over:
        over_label = font.render("GAME OVER - press SPACE to restart", True, (200, 30, 30))
        screen.blit(over_label, (WIDTH // 2 - over_label.get_width() // 2, HEIGHT // 2))

    pygame.display.flip()
    clock.tick(60)

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()