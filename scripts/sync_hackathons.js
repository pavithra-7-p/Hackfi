const admin = require("firebase-admin");
const axios = require("axios");

// Initialize Firebase Admin using the GitHub secret
const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

// Helper to strip all HTML tags from Devpost's prize strings
function cleanHtml(text) {
  if (!text) return "";
  return text.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}

function normalizeEvent(raw) {
  const title = raw.title || raw.name || "Collegiate Innovation Challenge";
  const docId = title.toLowerCase().replace(/[^a-z0-9]/g, "-").slice(0, 50);

  // Clean prize text from HTML
  let cleanPrize = cleanHtml(raw.prize_amount || raw.prize);
  if (!cleanPrize) {
    cleanPrize = "Cash Prizes & Merit Certificates";
  }

  // Ensure absolute HTTPS URL
  let targetUrl = raw.url || raw.siteUrl || "https://devpost.com/hackathons";
  if (targetUrl && !targetUrl.startsWith("http")) {
    targetUrl = `https://${targetUrl}`;
  }

  // Parse deadline safely
  let deadlineDate = raw.submission_period_dates || raw.deadline;
  let parsedDeadline = deadlineDate ? new Date(deadlineDate) : new Date(Date.now() + 20 * 24 * 60 * 60 * 1000);
  if (isNaN(parsedDeadline.getTime()) || parsedDeadline < new Date()) {
    parsedDeadline = new Date(Date.now() + 25 * 24 * 60 * 60 * 1000);
  }

  return {
    docId,
    data: {
      title: title,
      organizer: raw.organization_name || raw.organizer || "Collegiate Partner",
      mode: (raw.displayed_location?.location || raw.mode || "ONLINE").toUpperCase().includes("ONLINE") ? "ONLINE" : "OFFLINE",
      prize: cleanPrize,
      prizeValue: parseInt(cleanPrize.replace(/[^0-9]/g, "")) || 50000,
      deadline: admin.firestore.Timestamp.fromDate(parsedDeadline),
      startDate: admin.firestore.Timestamp.fromDate(new Date()),
      isInternational: Boolean(raw.is_international ?? true),
      isRecurring: false,
      tags: raw.themes?.map((t) => t.name) || raw.tags || ["Coding", "AI/ML", "Innovation"],
      // Populate all common field variations so Flutter finds the link regardless of field name
      siteUrl: targetUrl,
      url: targetUrl,
      registrationUrl: targetUrl,
      link: targetUrl,
      posterUrl: raw.thumbnail_url || raw.posterUrl || "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=800&q=80",
      lastSyncedAt: admin.firestore.FieldValue.serverTimestamp(),
    },
  };
}

async function runAutoSync() {
  console.log("==> Running Autonomous Daily Hackathon Ingestion...");

  try {
    const response = await axios.get(
      "https://devpost.com/api/hackathons?challenge_type[]=online&status[]=upcoming&status[]=open",
      { headers: { "User-Agent": "Mozilla/5.0" } }
    );

    const hackathonsList = response.data?.hackathons || [];
    console.log(`Fetched ${hackathonsList.length} live hackathons.`);

    if (hackathonsList.length === 0) {
      console.log("No new hackathons found in today's scrape.");
      return;
    }

    const batch = db.batch();

    hackathonsList.slice(0, 15).forEach((rawItem) => {
      const { docId, data } = normalizeEvent(rawItem);
      const docRef = db.collection("hackathons").doc(docId);
      batch.set(docRef, data, { merge: true });
    });

    await batch.commit();
    console.log("✔ Daily sync finished successfully. Firestore is fully updated!");
  } catch (err) {
    console.error("Sync error:", err.message);
    process.exit(1);
  }
}

runAutoSync();
