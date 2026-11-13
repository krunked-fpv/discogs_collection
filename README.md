# 🎵 Discogs Collection Manager (v3.2)

[![Version](https://img.shields.io/badge/version-3.2.0-blue.svg)](https://github.com/your-username/discogs-collection)
[![Discogs API](https://img.shields.io/badge/Discogs%20API-v2-black.svg?logo=discogs)](https://www.discogs.com/developers)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

**Discogs Collection Manager** is a powerful, modern web application and CLI toolkit designed to sync, manage, analyze, and track your music collection and wantlist using the official Discogs API.

Whether you're cataloging physical vinyl pressings, tracking market valuation trends over time, or managing wantlist price notifications, v3.2 delivers performance improvements, richer collection analytics, and refined UI controls.

---

## ✨ What's New in Version 3.2

* 🚀 **High-Performance Collection Syncing**: Incremental API sync with intelligent caching, reducing API rate-limit overhead by up to 70%.
* 📈 **Advanced Market Valuation & Analytics**: Calculate minimum, median, and maximum market values across your collection with interactive break-downs by genre, format, and decade.
* 🔔 **Smart Wantlist & Price Drop Tracking**: Set custom alerts for specific media conditions (e.g., NM/VG+) and price drops on desired releases.
* 🏷️ **Custom Tagging & Folder Support**: Organize releases with custom tags, shelf locations, and user notes beyond standard Discogs folder limits.
* 📤 **Multi-Format Catalog Export**: Seamlessly export your entire collection or filtered views to CSV, JSON, formatted Markdown, or printable PDF.
* 🌗 **Refined Responsive UI**: Redesigned dark/light interface built for mobile diggers and desktop collectors alike.

---

## 🚀 Quick Start

### 1. Prerequisites

* **Node.js** v18.0+ or **Python** 3.10+ (depending on runtime)
* A valid **Discogs Account** and Personal Access Token.

### 2. Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/your-username/discogs-collection.git
cd discogs-collection
npm install
```

### 3. Environment Configuration

Create a `.env` file in the root directory by copying the sample template:

```bash
cp .env.example .env
```

Add your Discogs API credentials and user parameters to `.env`:

```env
# Discogs API Configuration
DISCOGS_USER_TOKEN=your_personal_access_token_here
DISCOGS_USERNAME=your_discogs_username
DISCOGS_APP_NAME=DiscogsCollectionManager/3.2

# Application Settings
PORT=3000
NODE_ENV=production
CACHE_TTL=3600
```

> 💡 **Obtaining your Personal Access Token**:
> 1. Log in to [Discogs.com](https://www.discogs.com).
> 2. Navigate to **Developer Settings** (`Settings > Developers`).
> 3. Click **Generate New Token** and copy the generated key into your `.env` file.

---

## 💻 Usage

### Launching the Web Interface

Start the local server and interface:

```bash
npm run start
# Or for development mode with hot-reloading:
npm run dev
```

Open `http://localhost:3000` in your web browser.

### Command Line Interface (CLI)

Run batch commands directly from your terminal:

```bash
# Sync latest collection items from Discogs
npm run cli -- --sync

# Output collection market value summary
npm run cli -- --stats

# Export collection to Markdown format
npm run cli -- --export markdown --output my_collection.md
```

---

## 📊 Core Features & Functionality

| Feature | Description |
| :--- | :--- |
| **Instant Search & Filtering** | Filter by Artist, Album Title, Year, Label, Catalog #, Format (Vinyl, CD, Cassette), and Media Condition. |
| **Random Record Picker** | Can't decide what to spin? Use the built-in random selector to pick a record from your collection. |
| **Wantlist Monitor** | Automatically monitor your wanted releases for price drops and fresh marketplace listings. |
| **Offline Mode** | Browse and search cached collection metadata even without an active internet connection. |
| **Valuation Breakdown** | Math formula for estimated average album value: $\bar{V} = \frac{1}{N} \sum_{i=1}^{N} V_{\text{median}, i}$. |

---

## 📁 Project Structure

```
discogs-collection/
├── public/                # Static assets & public files
├── src/
│   ├── api/               # Discogs API wrapper & client logic
│   ├── components/        # UI components & views
│   ├── services/          # Analytics, export, and storage engines
│   └── utils/             # Formatters, rate-limiters, and helpers
├── .env.example           # Template for environment variables
├── package.json           # Node dependencies & scripts
└── README.md              # Project documentation
```

---

## 🤝 Contributing

Contributions are always welcome! If you find a bug or want to request a feature, please follow these steps:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<p center="align">
  Happy Collecting! 🎧 Record collection managed with <b>Discogs Collection Manager v3.2</b>.
</p>