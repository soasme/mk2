# Launchkey MK2 Programmer's Reference Guide
Version 1.01 — © Focusrite Audio Engineering LTD

---

## MIDI Ports

The Launchkey has **2 MIDI ports**:

| Port | Name |
|------|------|
| Port 1 | `Launchkey MIDI` — keys, pitch/mod wheels always send here |
| Port 2 | `Launchkey InControl` — all LED control messages go here |

Unless otherwise stated, all **computer → Launchkey** communication goes to the **InControl port**.

---

## Modes

### Basic Mode (default on connect)
- Pads, pots, sliders send out of the **MIDI port**
- Generic MIDI controller behaviour

### Extended (InControl) Mode
- Pads, pots, sliders send out of the **InControl port**
- Keys and pitch/mod wheels still use the MIDI port

### HUI Mode
- Third mode, only activatable from Basic mode
- All pots, sliders, buttons output from InControl port
- Exits back to Basic after 5-second heartbeat timeout

**State transitions:**
```
Basic ←→ Extended   (via online/offline message)
Basic ←→ HUI        (via heartbeat)
Extended → HUI      NOT possible
```

---

## Mode Change Messages

All sent to **InControl port**.

### Enter Extended Mode
```
MIDI Channel 16, Note C-1, Velocity 127
9Fh, 0Ch, 7Fh  (159, 12, 127)
```

### Exit Extended Mode
```
MIDI Channel 16, Note C-1, Velocity 0
9Fh, 0Ch, 00h  (159, 12, 0)
```

The Launchkey confirms by echoing the same message back on the InControl port.

### InControl Section Switches (in Extended mode)

| Section | Basic→InControl | InControl→Basic |
|---------|----------------|-----------------|
| Sliders (49/61 key) | Ch16 D-1 vel127 `9Fh,0Eh,7Fh` (159,14,127) | Ch16 D-1 vel0 `9Fh,0Eh,00h` (159,14,0) |
| Pots | Ch16 C#-1 vel127 `9Fh,0Dh,7Fh` (159,13,127) | Ch16 C#-1 vel0 `9Fh,0Dh,00h` (159,13,0) |
| Drum Pads | Ch16 D#-1 vel127 `9Fh,0Fh,7Fh` (159,15,127) | Ch16 D#-1 vel0 `9Fh,0Fh,00h` (159,15,0) |

### LED Status Inquiry
```
Send:    MIDI Channel 16, Note B-1, Velocity 0
         9Fh, 0Bh, 00h  (159, 11, 0)

Reply:   MIDI Channel 16, Note B-1, Velocity (0-15)
         9Fh, 0Bh, Velocity  (159, 11, Velocity)
```

Velocity bits in reply:

| Bit | Meaning |
|-----|---------|
| 3 | Drum-pads InControl Button LED |
| 2 | Pots InControl Button LED |
| 1 | Sliders InControl Button LED (49/61 only) |
| 0 | Mute/Solo Button LED (49/61 only) |

### HUI Heartbeat
```
Send (computer → Launchkey, InControl port):
  MIDI Channel 1, C-1, Velocity 0
  90h, 00h, 00h  (144, 0, 0)

Reply (Launchkey → computer):
  MIDI Channel 1, C-1, Velocity 127
  90h, 00h, 7Fh  (144, 0, 127)
```
Heartbeat must repeat; 5-second timeout causes exit to Basic mode.

---

## LED Lighting

Drum pads have **RGB LEDs**. Velocity/CC value selects colour from a lookup table (0 = off, 1–127 = colour index).

Key colours by index: 0=off, 3=white, 5=red, 64=green, 45=blue (see full colour table in original PDF, values 0–127).

### Pad Note Layout (Physical)

```
[ Pad 1  ][ Pad 2  ][ Pad 3  ][ Pad 4  ][ Pad 5  ][ Pad 6  ][ Pad 7  ][ Pad 8  ]  (Round)
[ Pad 9  ][ Pad 10 ][ Pad 11 ][ Pad 12 ][ Pad 13 ][ Pad 14 ][ Pad 15 ][ Pad 16 ]  (Round)
```

### Pad Note Numbers

| Pad | Note name | Basic mode note# | Extended mode note# |
|-----|-----------|-----------------|---------------------|
| 1 (top-left) | E1 | 28h (40) | 60h (96) |
| 2 | F1 | 29h (41) | 61h (97) |
| 3 | F#1 | 2Ah (42) | 62h (98) |
| 4 | G1 | 2Bh (43) | 63h (99) |
| 5 | C2 | 30h (48) | 64h (100) |
| 6 | C#2 | 31h (49) | 65h (101) |
| 7 | D2 | 32h (50) | 66h (102) |
| 8 | D#2 | 33h (51) | 67h (103) |
| 9 (bottom-left) | C1 | 24h (36) | 70h (112) |
| 10 | C#1 | 25h (37) | 71h (113) |
| 11 | D1 | 26h (38) | 72h (114) |
| 12 | D#1 | 27h (39) | 73h (115) |
| 13 | G#1 | 2Ch (44) | 74h (116) |
| 14 | A1 | 2Dh (45) | 75h (117) |
| 15 | A#1 | 2Eh (46) | 76h (118) |
| 16 (bottom-right) | B1 | 2Fh (47) | 77h (119) |
| Upper round pad | — | CC 68h (104) | Note 68h (104) |
| Lower round pad | — | CC 69h (105) | Note 78h (120) |

### Lighting Pads in Basic Mode

Send **Note On, MIDI channel 16** on the InControl port.

```
LED on  (bottom-left pad): 9Fh, 24h, <colour>  (159, 36, colour)
LED off (bottom-left pad): 9Fh, 24h, 00h       (159, 36, 0)
```

Round pads use **CC** (not Note):
```
LED on  (upper round): BFh, 68h, <colour>  (191, 104, colour)
LED off (upper round): BFh, 68h, 00h       (191, 104, 0)
```

### Lighting Pads in Extended (InControl) Mode

Send **Note On, MIDI channel 16** on the InControl port, using extended note numbers.

```
LED on  (bottom-left pad): 9Fh, 70h, <colour>  (159, 112, colour)
LED off (bottom-left pad): 9Fh, 70h, 00h       (159, 112, 0)
```

Round pads use **CC** in extended mode too:
```
LED on  (upper round): BFh, 68h, <colour>  (191, 104, colour)
LED off (upper round): BFh, 68h, 00h       (191, 104, 0)
```

### Reset All Pad LEDs
```
MIDI Channel 16, CC 0, Value 0
BFh, 00h, 00h  (191, 0, 0)
```
Happens automatically when switching between Basic and InControl mode.

### Flashing LEDs

Same note/CC numbers as lighting, but sent on **MIDI channel 2** instead of 16. Syncs to MIDI clock (default 120 BPM). Each colour lasts half a beat: B → A → B → A.

To stop flashing: send any lighting message (on or off) on channel 16 to the same pad.

```
Flash top-left pad (Basic mode):
  91h, 28h, <colourB>  (145, 40, colourB)

Stop flash:
  9Fh, 28h, 00h        (159, 40, 0)
```

### Pulsing LEDs

Single colour that ramps 25%→100% brightness. Full cycle = 2 beats. Syncs to MIDI clock.

Same note/CC numbers as lighting, sent on **MIDI channel 3** instead of 16.

To stop pulsing: send a lighting off message on channel 16.

```
Pulse bottom-right round pad (Basic mode):
  B2h, 69h, <colour>  (178, 105, colour)

Stop pulse:
  BFh, 69h, 00h       (191, 105, 0)

Pulse 4th pad top row (Extended mode):
  92h, 63h, <colour>  (146, 99, colour)

Stop pulse:
  9Fh, 63h, 05h       (159, 99, colour)
```

### Mute/Solo Button LED (49/61 key only)
Red LED only. No flash/pulse support. Auto-off on Basic mode return.
```
On:  BFh, 3Bh, 7Fh  (191, 59, 127)
Off: BFh, 3Bh, 00h  (191, 59, 0)
```

---

## Summary: LED Channel Rules

| Channel | Purpose |
|---------|---------|
| 16 | Solid lighting (on/off) |
| 2  | Flashing (between colour A already set and new colour B) |
| 3  | Pulsing (brightness ramp, single colour) |

---

## Universal Device Inquiry

Can be sent to any Launchkey MIDI port.

```
Send:  F0h, 7Eh, 7Fh, 06h, 01h, F7h
       (240, 126, 127, 6, 1, 247)

Reply: F0h, 7Eh, 00h, 06h, 02h, 00h, 20h, 29h, 7Ah, 00h, FM1, FM2, R1, R2, R3, R4, F7h
```

- `00h 20h 29h` = Novation EMS manufacturer ID
- `7Ah 00h` = Launchkey MK2 product ID
- FM1 (key size): 00h=25-key, 01h=49-key, 02h=61-key; FM2 always 00h
- R1–R4 = firmware version digits (thousands, hundreds, tens, units)

---

## MIDI Reference: Launchkey → Computer (Input)

| Control | Message Type | Number (hex/dec) | Range |
|---------|-------------|------------------|-------|
| Pot 1 | CC | 15h (21) | 0–127 |
| Pot 2 | CC | 16h (22) | 0–127 |
| Pot 3 | CC | 17h (23) | 0–127 |
| Pot 4 | CC | 18h (24) | 0–127 |
| Pot 5 | CC | 19h (25) | 0–127 |
| Pot 6 | CC | 1Ah (26) | 0–127 |
| Pot 7 | CC | 1Bh (27) | 0–127 |
| Pot 8 | CC | 1Ch (28) | 0–127 |
| Slider 1 (49/61) | CC | 29h (41) | 0–127 |
| Slider 2 (49/61) | CC | 2Ah (42) | 0–127 |
| Slider 3 (49/61) | CC | 2Bh (43) | 0–127 |
| Slider 4 (49/61) | CC | 2Ch (44) | 0–127 |
| Slider 5 (49/61) | CC | 2Dh (45) | 0–127 |
| Slider 6 (49/61) | CC | 2Eh (46) | 0–127 |
| Slider 7 (49/61) | CC | 2Fh (47) | 0–127 |
| Slider 8 (49/61) | CC | 30h (48) | 0–127 |
| Slider 9/Master | CC | 07h (7) | 0–127 |
| Pad 1 Basic/Extended | Note | 28h (40) / 60h (96) | 0–127 |
| Pad 2 Basic/Extended | Note | 29h (41) / 61h (97) | 0–127 |
| Pad 3 Basic/Extended | Note | 2Ah (42) / 62h (98) | 0–127 |
| Pad 4 Basic/Extended | Note | 2Bh (43) / 63h (99) | 0–127 |
| Pad 5 Basic/Extended | Note | 30h (48) / 64h (100) | 0–127 |
| Pad 6 Basic/Extended | Note | 31h (49) / 65h (101) | 0–127 |
| Pad 7 Basic/Extended | Note | 32h (50) / 66h (102) | 0–127 |
| Pad 8 Basic/Extended | Note | 33h (51) / 67h (103) | 0–127 |
| Pad 9 Basic/Extended | Note | 24h (36) / 70h (112) | 0–127 |
| Pad 10 Basic/Extended | Note | 25h (37) / 71h (113) | 0–127 |
| Pad 11 Basic/Extended | Note | 26h (38) / 72h (114) | 0–127 |
| Pad 12 Basic/Extended | Note | 27h (39) / 73h (115) | 0–127 |
| Pad 13 Basic/Extended | Note | 2Ch (44) / 74h (116) | 0–127 |
| Pad 14 Basic/Extended | Note | 2Dh (45) / 75h (117) | 0–127 |
| Pad 15 Basic/Extended | Note | 2Eh (46) / 76h (118) | 0–127 |
| Pad 16 Basic/Extended | Note | 2Fh (47) / 77h (119) | 0–127 |
| Upper Round Pad Basic/Extended | CC/Note | 68h (104) / 68h (104) | 0/127 |
| Lower Round Pad Basic/Extended | CC/Note | 69h (105) / 78h (120) | 0/127 |
| Button 1–9 (49/61) | CC | 33h–3Bh (51–59) | 0/127 |
| Track Left | CC | 67h (103) | 0/127 |
| Track Right | CC | 66h (102) | 0/127 |
| Rewind | CC | 70h (112) | 0/127 |
| Fast Forward | CC | 71h (113) | 0/127 |
| Stop | CC | 72h (114) | 0/127 |
| Play | CC | 73h (115) | 0/127 |
| Loop | CC | 74h (116) | 0/127 |
| Record | CC | 75h (117) | 0/127 |
| Play Button 1 (PadSelect) | CC | 6Ch (108) | 0/127 |
| Play Button 2 (KeySelect) | CC | 6Dh (109) | 0/127 |

---

## MIDI Reference: Computer → Launchkey (LED/Mode Control)

All on **InControl port**.

| Function | Channel | Type | Number | Value |
|----------|---------|------|--------|-------|
| Set Extended mode on | 16 | Note | 0Ch (12) | 7Fh (127) |
| Set Extended mode off | 16 | Note | 0Ch (12) | 00h (0) |
| Square pad light Basic | 16 | Note | 24h–33h (36–51) | 0–127 |
| Round pad light Basic | 16 | CC | 68h/69h (104/105) | 0–127 |
| Square pad light Extended | 16 | Note | 60h–67h / 70h–77h (96–103 / 112–119) | 0–127 |
| Round pad light Extended | 16 | Note | 68h/78h (104/120) | 0–127 |
| Square pad flash Basic | 2 | Note | 24h–33h (36–51) | 0–127 |
| Round pad flash Basic | 2 | CC | 68h/69h (104/105) | 0–127 |
| Square pad flash Extended | 2 | Note | 60h–67h / 70h–77h (96–103 / 112–119) | 0–127 |
| Round pad flash Extended | 2 | Note | 68h/78h (104/120) | 0–127 |
| Square pad pulse Basic | 3 | Note | 24h–33h (36–51) | 0–127 |
| Round pad pulse Basic | 3 | CC | 68h/69h (104/105) | 0–127 |
| Square pad pulse Extended | 3 | Note | 60h–67h / 70h–77h (96–103 / 112–119) | 0–127 |
| Round pad pulse Extended | 3 | Note | 68h/78h (104/120) | 0–127 |
| Reset all pad LEDs | 16 | CC | 00h (0) | 00h (0) |
| Mute/Solo LED (49/61) | 16 | CC | 3Bh (59) | 0/127 |
| Pot section InControl on/off | 16 | Note | 0Dh (13) | 0/127 |
| Slider section InControl on/off | 16 | Note | 0Eh (14) | 0/127 |
| Drum pad section InControl on/off | 16 | Note | 0Fh (15) | 0/127 |
| LED status inquiry | 16 | Note | 0Bh (11) | 00h (0) |
