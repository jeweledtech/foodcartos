# FoodCartOS Hardware Guide

This guide covers the physical hardware installed in each food cart. The hardware enables offline-capable operation, GPS tracking, photo verification, and optional foot traffic counting.

**Estimated cost:** $150-400 per cart depending on configuration
**Installation time:** 2-4 hours

---

## Hardware Overview

### Minimum Viable Setup ($150)

| Component | Purpose | Cost |
|-----------|---------|------|
| Raspberry Pi 4 (4GB) | Main compute unit | $55 |
| 32GB microSD card | Storage | $10 |
| USB-C power supply | Power | $15 |
| Pi Camera Module v2 | Photo verification | $25 |
| Weatherproof enclosure | Protection | $25 |
| USB cellular modem | Internet | $20 |

### Recommended Setup ($300)

| Component | Purpose | Cost |
|-----------|---------|------|
| Raspberry Pi 4 (8GB) | Main compute unit | $75 |
| 64GB microSD card | Storage | $15 |
| USB-C power supply | Power | $15 |
| Pi Camera Module v2 | Photo verification | $25 |
| **SIM7600A-H HAT** | LTE + GPS combined | $80 |
| T-Mobile IoT SIM | Cellular service | $10/mo |
| Weatherproof enclosure | Protection | $40 |
| Dual antennas (LTE + GPS) | Better signal | $20 |
| Heat sinks + fan | Thermal management | $10 |

### Full Setup ($400+)

All of the above, plus:

| Component | Purpose | Cost |
|-----------|---------|------|
| 7" touchscreen display | Operator interface | $70 |
| ESP32-S3 XIAO | WiFi/BT foot traffic | $15 |
| External antenna mount | Better reception | $15 |

---

## Component Details

### Raspberry Pi 4

The brain of the cart system. Runs FoodCartOS agent, local SQLite database, and coordinates all hardware.

**Why Pi 4?**
- Sufficient processing power for image capture and local processing
- Built-in WiFi for initial setup and backup connectivity
- GPIO pins for HAT connection
- Large community support

**Specs to look for:**
- 4GB RAM minimum (8GB recommended)
- 64-bit capable
- Raspberry Pi OS Lite (no desktop needed)

**Mounting:**
- Use standoffs to mount inside weatherproof enclosure
- Ensure ventilation or add fan for hot days
- Keep away from heat sources (grills, steamers)

### SIM7600A-H HAT

Combined cellular modem and GPS receiver. This is the recommended connectivity solution.

**Features:**
- LTE Cat 4 (150 Mbps down, 50 Mbps up)
- Built-in GPS with 2.5m accuracy
- Works with T-Mobile, AT&T in US
- Connects directly to Pi GPIO header

**Why this over USB modem?**
- Single unit for both cellular and GPS
- More reliable connection (no USB issues)
- Better antenna options
- Cleaner installation

**Antenna setup:**
- LTE antenna: Mount on cart roof or high point
- GPS antenna: Must have clear sky view
- Use SMA extension cables if needed

### T-Mobile IoT SIM

Low-cost cellular data for cart connectivity.

**Plan:** T-Mobile IoT Data Plan
- $10/month for 5GB data
- No contract
- Coverage across US

**Data usage estimate:**
- Photos: ~500KB each × 10/day = 5MB
- Transactions: ~1KB each × 50/day = 50KB
- Location pings: ~100 bytes × 288/day = 30KB
- **Total: ~200MB/month typical**

5GB is more than enough, with room for video if added later.

### Camera Module

For photo verification of quality checks.

**Pi Camera Module v2:**
- 8MP resolution (plenty for verification)
- Connects via ribbon cable
- Small and easy to mount
- ~$25

**Mounting considerations:**
- Mount where operator can easily photograph:
  - Food prep area (for garlic butter buns)
  - Water setup (for dirty water verification)
  - Cart overview (for cleanliness check)
- Protect from steam and grease
- Consider adjustable mount for different angles

**Alternative: USB webcam**
- Logitech C270 or similar
- Easier to position
- More durable
- Slightly more expensive ($30-40)

### Weatherproof Enclosure

The Pi and HAT need protection from:
- Rain and moisture
- Dust and debris
- Extreme temperatures
- Accidental damage

**Recommended: IP65-rated enclosure**
- Dimensions: At least 200mm × 150mm × 75mm
- Cable glands for antenna and power cables
- Mounting holes for Pi standoffs

**Installation:**
- Mount inside cart, not outside
- Near power source (12V from cart or extension)
- Allow airflow (don't completely seal)
- Keep accessible for troubleshooting

### Optional: 7" Touchscreen

Provides an operator interface mounted in the cart.

**Official Raspberry Pi 7" Touchscreen:**
- 800×480 resolution
- Capacitive touch
- Connects via DSI + USB power
- ~$70

**Use cases:**
- View today's assignment
- Submit checklist photos
- See real-time sales
- Quick messaging

**Without touchscreen:**
Operators use their phone (PWA app) instead. This is often simpler and preferred.

### Optional: ESP32-S3 XIAO

Tiny microcontroller for passive foot traffic counting.

**How it works:**
1. ESP32 scans for WiFi networks and Bluetooth beacons
2. Counts unique device MACs (hashed for privacy)
3. Reports count to Pi via serial
4. Pi correlates with revenue to measure conversion

**Why optional?**
- Advanced feature, not needed for MVP
- Requires additional wiring and programming
- Value comes from statistical analysis over time

**Setup:**
- Connect to Pi via USB serial
- Power from Pi USB port
- Mount antenna for better reception

---

## Installation Steps

### Step 1: Prepare the Raspberry Pi

```bash
# On your computer:
# 1. Download Raspberry Pi Imager
# 2. Flash "Raspberry Pi OS Lite (64-bit)" to SD card
# 3. Enable SSH in imager settings
# 4. Set username/password
# 5. Configure WiFi for initial setup

# Insert SD card into Pi and power on
```

### Step 2: Initial Pi Configuration

```bash
# SSH into the Pi
ssh pi@raspberrypi.local  # or IP address

# Update system
sudo apt update && sudo apt upgrade -y

# Enable camera
sudo raspi-config
# Interface Options → Camera → Enable

# Enable serial for SIM7600
# Interface Options → Serial → No (login shell) → Yes (hardware)

# Reboot
sudo reboot
```

### Step 3: Install FoodCartOS Agent

```bash
# Install agent via script
curl -fsSL https://raw.githubusercontent.com/yourusername/foodcartos/main/hardware/install.sh | sudo bash

# This installs:
# - Python dependencies
# - FoodCartOS agent service
# - SQLite database
# - Camera utilities
# - Cellular/GPS tools
```

### Step 4: Configure SIM7600A-H

```bash
# Attach HAT to Pi GPIO header
# Insert SIM card (gold contacts down)
# Connect antennas

# Test cellular connection
sudo /opt/foodcartos/scripts/test-cellular.sh

# Expected output:
# Modem found: SIM7600A-H
# SIM status: Ready
# Signal strength: 18 (Good)
# Network: T-Mobile
# IP: 10.x.x.x

# Test GPS
sudo /opt/foodcartos/scripts/test-gps.sh

# Expected output:
# GPS fix: 3D
# Latitude: 38.3566
# Longitude: -121.9877
# Accuracy: 2.3m
```

### Step 5: Configure Camera

```bash
# Test camera
raspistill -o test.jpg

# View test image (copy to your computer)
scp pi@raspberrypi.local:test.jpg .

# If using USB webcam instead:
fswebcam -r 1280x720 test.jpg
```

### Step 6: Register Cart

```bash
# Run registration script
sudo /opt/foodcartos/scripts/register-cart.sh

# Follow prompts:
# 1. Enter organization ID (from FoodCartOS dashboard)
# 2. Enter cart name (e.g., "Cart 1 - Main")
# 3. Confirm registration

# This:
# - Generates unique hardware ID
# - Registers with cloud database
# - Downloads configuration
# - Starts sync service
```

### Step 7: Verify Installation

```bash
# Check service status
sudo systemctl status foodcartos-agent

# Check logs
sudo journalctl -u foodcartos-agent -f

# Verify cloud sync
curl http://localhost:8080/status

# Expected:
# {
#   "cart_id": "abc123",
#   "online": true,
#   "last_sync": "2024-01-15T10:30:00Z",
#   "gps": {"lat": 38.3566, "lng": -121.9877},
#   "cellular": {"signal": 18, "carrier": "T-Mobile"}
# }
```

---

## Physical Installation in Cart

### Power Setup

**Option A: Cart's 12V system**
- Use 12V to USB-C converter
- Connect to cart's battery or electrical system
- Add fuse for protection

**Option B: Dedicated battery pack**
- Large USB battery bank (20,000+ mAh)
- Charge overnight
- Lasts full shift (8-12 hours)

**Option C: Extension cord**
- Run from location's power outlet
- Most reliable but limits placement
- Good for fixed locations

### Mounting Locations

```
         ┌─────────────────────────────────────┐
         │            FOOD CART                │
         │                                     │
         │    ┌─────────┐                      │
         │    │ SCREEN  │  (optional)          │
         │    │(7" touch│                      │
         │    └─────────┘                      │
         │                                     │
         │    ┌──────────────────────┐         │
         │    │     PREP AREA        │         │
         │    │                      │         │
         │    │  📷 Camera aimed     │         │
         │    │     at this area     │         │
         │    └──────────────────────┘         │
         │                                     │
         │                      ┌─────────┐    │
         │                      │   PI    │    │
         │                      │ENCLOSURE│    │
         │                      └─────────┘    │
         │                                     │
         │    ════════════════════════         │
         │         SERVING COUNTER             │
         └─────────────────────────────────────┘

         Roof/Top:
         ┌─────────────────────────────────────┐
         │  📡 LTE Antenna    📡 GPS Antenna   │
         └─────────────────────────────────────┘
```

### Cable Management

- Use cable clips to secure all wires
- Coil excess cable neatly
- Keep cables away from heat sources
- Use cable glands where wires enter enclosure

### Environmental Considerations

**Heat:**
- Food carts get hot (grills, steamers, summer sun)
- Add heat sinks to Pi CPU
- Include small fan in enclosure
- Mount away from cooking equipment

**Moisture:**
- Steam from cooking
- Rain exposure when opening cart
- Use conformal coating on exposed electronics
- Seal enclosure cable entries

**Vibration:**
- Carts move and shake
- Use lock washers on mounting screws
- Secure all cable connections
- Check monthly for loosening

---

## Troubleshooting

### "No cellular connection"

1. Check SIM card seated properly
2. Verify SIM is activated with carrier
3. Check antenna connections
4. Test in different location (signal strength)
5. Check AT command response: `sudo minicom -D /dev/ttyUSB2`

### "GPS not getting fix"

1. Ensure GPS antenna has clear sky view
2. Wait 2-3 minutes for cold start fix
3. Check antenna cable connection
4. Move antenna to better location (roof ideal)

### "Camera not working"

1. Check ribbon cable connection (both ends)
2. Verify camera enabled in raspi-config
3. Test with `raspistill -o test.jpg`
4. Check for physical damage to cable

### "Agent not syncing"

1. Check cellular connection: `ping google.com`
2. Verify API endpoint reachable: `curl https://your-api.com/health`
3. Check local database: `sqlite3 /opt/foodcartos/data/cart.db`
4. Review logs: `sudo journalctl -u foodcartos-agent`

### "Pi keeps rebooting"

1. Power supply insufficient (use official 3A supply)
2. Overheating (add fan, improve ventilation)
3. Corrupted SD card (re-flash, use quality card)
4. Check logs before crash: `sudo journalctl --since yesterday`

---

## Maintenance Schedule

### Daily
- [ ] Verify sync status (green indicator in app)
- [ ] Check camera lens is clean
- [ ] Ensure enclosure is closed

### Weekly
- [ ] Check antenna connections
- [ ] Verify cable routing (no damage)
- [ ] Review error logs
- [ ] Clean camera lens

### Monthly
- [ ] Tighten mounting screws
- [ ] Check for moisture in enclosure
- [ ] Update system packages
- [ ] Backup local database

### Quarterly
- [ ] Full system test (all components)
- [ ] Replace thermal paste if needed
- [ ] Check battery health (if applicable)
- [ ] Review and apply agent updates

---

## Parts List with Links

### Essential

| Part | Link | Price |
|------|------|-------|
| Raspberry Pi 4 (8GB) | [raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/) | $75 |
| 64GB microSD | [Amazon](https://www.amazon.com/) | $15 |
| Official USB-C Power Supply | [raspberrypi.com](https://www.raspberrypi.com/products/type-c-power-supply/) | $15 |
| Pi Camera Module v2 | [raspberrypi.com](https://www.raspberrypi.com/products/camera-module-v2/) | $25 |
| SIM7600A-H HAT | [Waveshare](https://www.waveshare.com/sim7600a-h-4g-hat.htm) | $80 |
| T-Mobile IoT SIM | [T-Mobile](https://www.t-mobile.com/business/iot) | $10/mo |
| LTE + GPS Antennas | [Amazon](https://www.amazon.com/) | $20 |
| Weatherproof Enclosure | [Amazon](https://www.amazon.com/) | $40 |

### Optional

| Part | Link | Price |
|------|------|-------|
| 7" Touchscreen | [raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-touch-display/) | $70 |
| ESP32-S3 XIAO | [Seeed Studio](https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html) | $15 |
| Heat Sink Kit | [Amazon](https://www.amazon.com/) | $8 |
| Cooling Fan | [Amazon](https://www.amazon.com/) | $10 |

---

## Next Steps

1. [Configure the agent](./agent-config.md)
2. [Set up offline sync](./offline-sync.md)
3. [Camera calibration](./camera-setup.md)
4. [GPS accuracy tuning](./gps-tuning.md)
