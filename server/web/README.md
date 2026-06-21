# PRESCRIPTION — Web UI Dashboard

A responsive, single-page application (SPA) built to provide healthcare
providers with a modern, real-time interface to record doctor-patient
conversations, track transcription and AI processing pipeline, verify
extracted medication details, and export clinical PDF prescriptions.

---

## 📱 Device Compatibility & Responsiveness

The Web UI has been optimized for both large screens (laptops/desktops)
and small screens (mobile devices down to 320px).

### 1. Laptop / Desktop Optimization
- **Grid Layouts**: Two-column layouts for high-density information display
  (e.g., side-by-side Recording & Configuration cards, Session Summary &
  PDF Export options).
- **Navigation**: Clean horizontal header navigation tabs with sticky top
  positioning for instant stage switches.
- **Tables**: Complete multi-column medication tables (Medicine Name,
  Dosage, Frequency, Duration, Instructions, Price, Manufacturer)
  displayed side-by-side.

### 2. Mobile / Portrait Optimization (<= 768px)
- **Responsive Padding**: Container padding drops from 24px to 12px, and
  card padding drops from 28px to 16px to maximize horizontal reading area.
- **Scrollable Header Tabs**: The header wraps gracefully, and the tab list
  scrolls horizontally if overflow occurs, hiding scrollbars for a native
  app-like feel.
- **Single-Column Config Grid**: At widths <= 480px, the 2x2 configuration
  grid shifts to a vertical stacked list. Each config element transitions
  to a horizontal `row` layout (label on left, value on right) preventing
  any text truncation or offscreen clipping.
- **Stacked Summary Grid**: Summary details in the Export tab stack
  vertically at <= 480px.
- **Vertical Patient Information**: Patient fields stack into a single
  column at <= 400px width.
- **Horizontal Table Scrolling**: The medication table is enclosed in a
  responsive wrapper that enables horizontal touch scrolling, ensuring all
  medical fields remain reviewable without breaking the page width.

---

## 🛠️ Technology Stack
- **Frontend**: Vanilla HTML5, CSS3 variables, and ES6 JavaScript.
- **Styling**: Modern, premium dark-mode theme utilizing glassmorphism and
  smooth CSS transitions.
- **Backend API**: FastAPI serving endpoints for session state, voice upload,
  STT/LLM pipeline runs, and PDF downloads.
- **Server Dev**: Uvicorn.

---

## 🚀 How to Run the Web UI

To launch the web interface, execute the following command:

```bash
uv run prescription-web
```

Once running, navigate to:
[http://localhost:8000](http://localhost:8000)
