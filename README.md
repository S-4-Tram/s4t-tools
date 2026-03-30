# Trampoline Gymnast Programme Generator

A simple command-line tool that generates a personalised weekly strength and conditioning plan for trampoline gymnasts.

---

## Requirements

- Python 3.7 or newer
- No third-party libraries needed — uses only the Python standard library

---

## How to run

1. Open a terminal and navigate to the folder containing the script:

   ```bash
   cd /path/to/s4t-tools
   ```

2. Run the script:

   ```bash
   python3 programme_generator.py
   ```

3. Answer the questions when prompted:

   | Question | Example answer |
   |---|---|
   | Athlete name | Jamie Smith |
   | Programme type | Repeated Power |
   | Week number | 2 |
   | Main sessions per week | 3 |
   | Micro-dose sessions per week | 2 |

4. Your programme is printed to the screen **and** saved automatically to `weekly_programme.txt`.

---

## Training focus options

| # | Focus | Good for |
|---|---|---|
| 1 | Force production | Building explosive power for bigger jumps |
| 2 | Trunk stiffness | Improving body tension and shape in the air |
| 3 | Overhead strength | Shoulder stability and pressing strength |
| 4 | General preparation | All-round conditioning and movement quality |

---

## Session types

**Main session** (~45–60 mins)
Includes a structured warm-up, exercises for quads, calves, and trunk, and a cool-down. Load and intensity are guided by the chosen focus.

**Micro-dose session** (~15 mins)
A short daily activation block to maintain movement quality between main sessions. No warm-up required — keep intensity low.

---

## Output file

The programme is saved to `weekly_programme.txt` each time you run the script. Running the script again will overwrite the previous file, so rename or move it if you want to keep it.

---

## Customising the programme

All exercises are stored in the `EXERCISE_LIBRARY` dictionary in `data.py`. You can:

- Add or swap exercises by editing the lists under each focus area
- Adjust sets and reps by changing the text in those lists
- Add new focus areas by following the same dictionary structure

---

## Example output

```
================================================================
  WEEKLY STRENGTH & CONDITIONING PROGRAMME – TRAMPOLINE GYMNAST
================================================================
Athlete : Jamie Smith
Focus   : Force Production
Main sessions / week   : 3
Micro-dose sessions / week: 2
Total days of training : 5

--- DAY 1: MAIN SESSION 1/3 ---
Focus: Force Production

WARM-UP (10 mins)
  • 5 min light jog or skipping
  ...

QUADS
  • Barbell back squat – 4 x 5 @ 80% 1RM (focus on explosive drive)
  ...
```
