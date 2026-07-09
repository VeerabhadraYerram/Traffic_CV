---
version: alpha
name: Technical HUD (Swiss Precision)
description: A high-performance surveillance and ANPR operations center theme. It anchors on a deep obsidian canvas (`#080a0f`) and slate-gray card surfaces (`#0d111b`) separated by razor-thin, high-contrast borders (`#1e293b`). The brand voltage is driven by Signal Orange (`#ff6b00`) for interaction states and key statistics, Crimson Red (`#ef4444`) for hotlist alerts, and Emerald Green (`#00e676`) for verified vehicles. Typography uses highly structured Plus Jakarta Sans for UI controls and Geist Mono / JetBrains Mono for monospaced license plates, speeds, timestamps, and tabular numerical reports to eliminate layout shifts and cognitive friction.

colors:
  primary: "#ff6b00"
  primary-foreground: "#ffffff"
  background: "#080a0f"
  foreground: "#f8fafc"
  card: "#0d111b"
  card-foreground: "#f8fafc"
  popover: "#0d111b"
  popover-foreground: "#f8fafc"
  secondary: "#1a202c"
  secondary-foreground: "#e2e8f0"
  muted: "#151b26"
  muted-foreground: "#8a99ad"
  accent: "#1e2638"
  accent-foreground: "#f8fafc"
  destructive: "#ef4444"
  destructive-foreground: "#ffffff"
  success: "#00e676"
  success-foreground: "#080a0f"
  border: "#1e293b"
  input: "#151b26"
  ring: "#ff6b00"
  chart-1: "#ff6b00"
  chart-2: "#00e676"
  chart-3: "#00b0ff"
  chart-4: "#ffd600"
  chart-5: "#ef4444"

typography:
  display-lg:
    fontFamily: "'Plus Jakarta Sans', 'Geist Sans', sans-serif"
    fontSize: "36px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  display-md:
    fontFamily: "'Plus Jakarta Sans', 'Geist Sans', sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  display-sm:
    fontFamily: "'Plus Jakarta Sans', 'Geist Sans', sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body-lg:
    fontFamily: "'Plus Jakarta Sans', 'Geist Sans', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  body-md:
    fontFamily: "'Plus Jakarta Sans', 'Geist Sans', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "'Plus Jakarta Sans', 'Geist Sans', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  code-lg:
    fontFamily: "'Geist Mono', 'JetBrains Mono', monospace"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.2
  code-md:
    fontFamily: "'Geist Mono', 'JetBrains Mono', monospace"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.05em"
  code-sm:
    fontFamily: "'Geist Mono', 'JetBrains Mono', monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.2

rounded:
  none: "0px"
  xs: "2px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  full: "9999px"

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"

components:
  card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.sm}"
    border: "1px solid {colors.border}"
    padding: "16px"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.xs}"
    padding: "8px 16px"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-foreground}"
    rounded: "{rounded.xs}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.input}"
    rounded: "{rounded.xs}"
    border: "1px solid {colors.border}"
    padding: "8px 12px"
  badge-alert:
    backgroundColor: "rgba(239, 68, 68, 0.15)"
    textColor: "{colors.destructive}"
    rounded: "{rounded.xs}"
    border: "1px solid rgba(239, 68, 68, 0.3)"
  badge-success:
    backgroundColor: "rgba(0, 230, 118, 0.15)"
    textColor: "{colors.success}"
    rounded: "{rounded.xs}"
    border: "1px solid rgba(0, 230, 118, 0.3)"
---

# ANPR Dashboard Design Specification

## Overview
The Automatic Number Plate Recognition (ANPR) system is a mission-critical surveillance and analytics platform used by traffic operators and law enforcement. The design language must move away from generic SaaS interfaces (which are typically soft, rounded, and rely on purple or blue gradients) and align with **technical instrumentation and Swiss design principles**. 

This system prioritizes **precision, speed of recognition, and physical visual hierarchy**. The layout resembles a tactical cockpit, ensuring operators can scan massive feeds of vehicle events, cross-reference hotlist alerts, and analyze traffic volumes without eye strain or cognitive layout drift.

### Core Visual Dials
* **`DESIGN_VARIANCE: 4`** — Clean, structured grids. Highly aligned layouts that match maps and telemetry data.
* **`MOTION_INTENSITY: 5`** — Subtle spring animations for card entry and real-time logs, combined with alert pulses that guide focus without distracting.
* **`VISUAL_DENSITY: 8`** — A data-dense workspace. Information is tightly packaged to fit full situational awareness on single screens.

---

## Colors

The palette is anchored in a dark obsidian operations room canvas to minimize visual glare and fatigue. Color is treated as functional state rather than decoration.

* **Canvas base (`#080a0f`):** A deep obsidian canvas that acts as the background for the entire application.
* **Surfaces (`#0d111b`):** Slate-gray charcoal blocks that house lists, statistics, and maps. 
* **Borders (`#1e293b`):** Hard, razor-thin lines separating cards and panels, creating a grid-like layout structure.
* **Interactive Accent (`#ff6b00`):** Signal Orange is used exclusively for primary filters, selected items, active nodes, and key numeric totals. No purple or violet is permitted.
* **Alert / Violation (`#ef4444`):** Crimson Red for hotlisted vehicles, speed violations, and system warnings. 
* **Verified / Normal (`#00e676`):** Emerald Green for whitelisted plates, authorized entries, and normal camera status feeds.
* **Secondary Info (`#00b0ff`):** Cyan for search highlights, informational callouts, and secondary routes.

---

## Typography

Typography is split into two strict functional classes: **Sans-Serif (for UI context and navigation)** and **Monospace (for data and identifiers)**.

### Monospace Rule (Tabular Alphanumerics)
Surveillance monitoring requires reading strings of alphanumeric license plates and numbers (speeds, counts, times). Standard proportional fonts cause visual drift when numbers change (e.g., the number `1` is narrower than `8`, causing text blocks to shift).
* **Font:** `Geist Mono` or `JetBrains Mono` (with monospace fallbacks).
* **Application:** License plates, speeds, timestamps, IP addresses, coordinates, and chart tooltip values.
* **License Plate Styling:** Rendered as uppercase bold monospaced characters inside a rounded-xs container with a subtle metallic background, mimicking real-world plate geometry.

### Sans-Serif Rule (Controls and Labels)
* **Font:** `Plus Jakarta Sans` or `Geist Sans`.
* **Application:** Headers, navigation items, descriptive labels, and settings forms. Tighter letter-spacing is applied to display sizes to create an editorial, authoritative structure.

---

## Layout

The layout is built for real-time operation feeds rather than static landing pages.

### Dashboard Grid (3:1 Asymmetrical Split)
* **Stats Row:** Compact, horizontal cards showing active surveillance metrics.
* **Left Column (75% width):** Live events table, a flowing stream of license plate detections.
* **Right Column (25% width):** Sticky Real-time Alert Panel, featuring critical hotlist notifications that scroll independently.

### Tracking Page Overlay
* **Full-screen Map:** Google Maps canvas acting as the background.
* **Floating Panels:** Asymmetrical HUD controls. Search panel floats on the left; selected camera details and last-seen cards float on the right. 

---

## Elevation & Depth

No soft, blurry shadows are used to simulate card elevation. Shadows represent artificial depth that clashes with a technical HUD design.
* **Borders over Shadows:** Depth is defined by thin, high-contrast borders (`1px solid var(--border)`).
* **Opacity Scale:** Cards overlaying the map use a solid canvas fill or 95% opacity to maintain readable text against complex map visual data.
* **Indicator Pulses:** Real-time detections use a subtle spring scale animation and a border pulse indicator (`animate-pulse`) instead of glowing backdrop blurs.

---

## Shapes

To match the industrial instrumentation theme, the system uses sharp, geometric corners instead of friendly, rounded shapes.
* **Interactive Elements (Buttons, Inputs, Badges):** `radius: 2px` (Tailwind `rounded-[2px]`).
* **Content Surfaces (Cards, Tables, Map Overlays):** `radius: 4px` (Tailwind `rounded-[4px]`).
* **Active indicators:** Sharp geometric bars and micro-arrows.

---

## Components

All blocks are constructed from unstyled `radix-ui` primitives styled with Tailwind or customized `shadcn/ui` blocks.

### 1. Stats Card (Card)
* **Structure:** Clean 1px border card, containing a label, a large monospaced metric value, and a small badge showing the delta change.
* **Interaction:** Hovering triggers a subtle border color shift to `#ff6b00` (Signal Orange).

### 2. Live Events Stream (Table)
* **Structure:** High-density table with sticky header. Each row displays:
  - Timestamp (monospaced body-sm)
  - Raw plate snapshot image
  - License Plate string (styled like a real metal plate in a monospace badge)
  - Camera ID & Location
  - Confidence Score (percentage with color-coded warning bar)
* **Row Highlight:** Violation rows have a subtle left-accent border in crimson.

### 3. Alerts Panel (Alert)
* **Structure:** Distinct cards with a solid, high-contrast dark red background. Includes a red pulse indicator, raw plate text, matching criteria (e.g., "Hotlist - Stolen Vehicle"), and a visual link to the camera source.
* **Spring Animation:** New alerts slide down from the top using spring physics (`type: "spring", stiffness: 100`).

### 4. Filters Control Bar (Toggle Group)
* **Structure:** Flat, bordered bar containing compact toggles.
* **State:** Selected button uses active primary accent text and background tint, with a sharp `2px` focus ring.

### 5. Analytics Charts
* **Recharts styling:** Set against transparent backgrounds. Tooltips use slate-charcoal cards (`#0d111b`) with a `1px` border, containing tabular monospaced text to prevent sizing jumps.

---

## Do's and Don'ts

### Do's
* **Do** use `font-variant-numeric: tabular-nums` or `Geist Mono` for all numbers, speeds, timestamps, and coordinates.
* **Do** render license plates in uppercase bold monospace letters inside a physical-looking plate box container.
* **Do** keep cards and layouts sharp, using `2px` for buttons/badges and `4px` for cards.
* **Do** use Signal Orange (`#ff6b00`) as the exclusive primary accent color for active items and filters.

### Don'ts
* **Don't** use purple, violet, indigo, or mesh gradients anywhere in the interface.
* **Don't** use rounded corners larger than `8px` unless it is a full-pill button (e.g. `rounded-full` for map toggle icons).
* **Don't** use soft black shadows for card elevation. Use thin solid borders.
* **Don't** wrap license plate text onto multiple lines.
* **Don't** default to standard `Inter` sans-serif font for plate codes or metrics.
